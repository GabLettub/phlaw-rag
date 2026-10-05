"""Answer chains for each intent, and the dispatcher that runs them."""

import re

from groq import BadRequestError
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field

from app import cases, prompts, router, store
from app.llm import get_llm

# Only the most recent turns are sent to the LLM, to save tokens.
HISTORY_LIMIT = 6
# Notion rejects text blocks of about 2,000 characters, so stay under.
PARAGRAPH_LIMIT = 1800
SNIPPET_LENGTH = 300
# Output budgets. Reasoning tokens count toward them, so they are
# generous; a tight cap would cut the visible answer off.
DIGEST_MAX_TOKENS = 4096
ANSWER_MAX_TOKENS = 2048

# Ks here are used to control how many chunks of text the vector
# database retrieves for the LLM to use. The LLM will read them all and
# decide which are relevant to the question. The LLM is good at ignoring
# irrelevant chunks, so we can err on the side of retrieving more rather
# than fewer.
FOLLOW_UP_K = 6
# Footnotes and signature blocks are tagged "notes" at ingestion. They
# are mostly bare citations that match many queries by accident, so
# searches leave them out.
EXCLUDE_NOTES = {"$ne": "notes"}
# The disposition often answers "what did the Court decide / strike
# down" questions, but it rarely ranks high for them by similarity.
FOLLOW_UP_DISPOSITIVE_K = 2
SEARCH_CASES = 3
EXCERPTS_PER_CASE = 2
# When verifying a decline, look at every case but only its best
# excerpt. Dense scores cannot rank cases reliably for rare names, so
# cutting to the top few would hide the one that matches.
VERIFY_EXCERPTS_PER_CASE = 1
# Each query pulls a different part of the decision, so the digest sees
# the background, the reasoning and the disposition. The last query is
# capped at 3 chunks because a long disposition would
# otherwise crowd out the rest and exceed the token budget.
DIGEST_QUERIES = (
    ("antecedent facts and background of the petition", 5, None),
    ("issues raised and the Court's ruling and reasons", 5, None),
    ("WHEREFORE the petition is decided", 3, "dispositive"),
)

# Structured output sometimes fails because the model writes prose
# instead of the requested JSON (Groq reports a 400). One retry with
# more reasoning effort usually succeeds.
RETRY_EFFORT = "high"

# Digests are slow and use up free-tier quota, so each is generated once
# per process and cleared when the case is re-ingested.
_digest_cache = {}


class DigestText(BaseModel):
    """The LLM's structured digest, before it is formatted."""

    facts: list[str] = Field(description="Short paragraphs of facts.")
    issues: list[str] = Field(description="Each starts 'Whether or not'.")
    ruling: list[str] = Field(description="Disposition and reasons.")
    doctrine: list[str] = Field(description="Principles the case states.")


class SearchMatch(BaseModel):
    """One case the verifier judged to match the question."""

    case_id: str = Field(description="Exact case_id of the candidate.")
    reason: str = Field(description="One sentence on why it matches.")


class SearchResult(BaseModel):
    """The verifier's verdict: the matching cases, possibly none."""

    matches: list[SearchMatch] = Field(default_factory=list)


def invoke_structured(prompt, schema, variables, max_tokens):
    """Run a prompt and return an instance of schema.

    Use json_schema mode, which is more reliable on Groq than function
    calling. If the model still answers in prose, retry once at
    RETRY_EFFORT before giving up and re-raising the error.
    """
    for effort in (None, RETRY_EFFORT):
        llm = get_llm("answer", max_tokens=max_tokens, effort=effort)
        structured = llm.with_structured_output(schema, method="json_schema")
        try:
            return (prompt | structured).invoke(variables)
        except BadRequestError:
            if effort == RETRY_EFFORT:
                raise


def format_excerpts(docs):
    """Join documents into a labelled block the prompts can quote from."""
    blocks = []
    for doc in docs:
        meta = doc.metadata
        label = f"[{meta['title']}, {meta['gr_no']}, {meta['section']}]"
        blocks.append(f"{label}\n{doc.page_content}")
    return "\n\n---\n\n".join(blocks)


def to_sources(docs):
    """Turn retrieved documents into the source dicts returned to users."""
    sources = []
    seen = set()
    for doc in docs:
        meta = doc.metadata
        key = (meta["case_id"], int(meta["chunk_index"]))
        if key in seen:
            continue
        seen.add(key)
        snippet = doc.page_content[:SNIPPET_LENGTH]
        if len(doc.page_content) > SNIPPET_LENGTH:
            snippet += "..."
        sources.append(
            {
                "case_id": meta["case_id"],
                "title": meta["title"],
                "gr_no": meta["gr_no"],
                "section": meta["section"],
                "snippet": snippet,
                "url": meta["url"],
            }
        )
    return sources


def unique_docs(docs):
    """Drop repeated chunks, keeping the first of each and the order."""
    seen = set()
    unique = []
    for doc in docs:
        key = (doc.metadata["case_id"], int(doc.metadata["chunk_index"]))
        if key not in seen:
            seen.add(key)
            unique.append(doc)
    return unique


def to_messages(history):
    """Convert the last HISTORY_LIMIT chat messages to LangChain messages."""
    messages = []
    for item in history[-HISTORY_LIMIT:]:
        cls = HumanMessage if item.role == "user" else AIMessage
        messages.append(cls(content=item.content))
    return messages


def split_paragraph(text, limit=PARAGRAPH_LIMIT):
    """Split text into pieces of at most limit characters.

    Break at sentence ends where possible. A single sentence longer
    than limit is cut hard, since the limit is a downstream requirement.
    """
    pieces = []
    current = ""
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        while len(sentence) > limit:
            if current:
                pieces.append(current)
                current = ""
            pieces.append(sentence[:limit])
            sentence = sentence[limit:]
        if current and len(current) + 1 + len(sentence) > limit:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def retrieve_for_digest(case_id):
    """Fetch the excerpts a digest is written from, in reading order.

    Run each query in DIGEST_QUERIES filtered to the case, merge the
    results without duplicates and sort by chunk_index.
    """
    vector_store = store.get_vector_store()
    found = {}
    for query, k, section in DIGEST_QUERIES:
        search_filter = {
            "case_id": case_id,
            "section": section or EXCLUDE_NOTES,
        }
        for doc in vector_store.similarity_search(
            query, k=k, filter=search_filter
        ):
            found[int(doc.metadata["chunk_index"])] = doc
    return [found[index] for index in sorted(found)]


def build_digest(case_id):
    """Return the digest dict for a case (the /digest response shape).

    The result has the case id, title, G.R. number, four sections of
    paragraphs (Facts, Issues, Ruling, Doctrine) and the source
    excerpts. It is cached per case_id.
    """
    if case_id in _digest_cache:
        return _digest_cache[case_id]
    docs = retrieve_for_digest(case_id)
    if not docs:
        raise LookupError(f"No indexed text for case {case_id}")
    # Title and G.R. number come from the chunks, so cases added through
    # /ingest work even though they are not in cases.yaml.
    meta = docs[0].metadata
    prompt = ChatPromptTemplate.from_messages(
        [("system", prompts.DIGEST_SYSTEM), ("human", prompts.DIGEST_USER)]
    )
    text = invoke_structured(
        prompt,
        DigestText,
        {
            "title": meta["title"],
            "gr_no": meta["gr_no"],
            "excerpts": format_excerpts(docs),
        },
        DIGEST_MAX_TOKENS,
    )
    sections = []
    for heading, items in (
        ("Facts", text.facts),
        ("Issues", text.issues),
        ("Ruling", text.ruling),
        ("Doctrine", text.doctrine),
    ):
        paragraphs = [p for item in items for p in split_paragraph(item)]
        sections.append({"heading": heading, "paragraphs": paragraphs})
    digest = {
        "case_id": case_id,
        "title": meta["title"],
        "gr_no": meta["gr_no"],
        "sections": sections,
        "sources": to_sources(docs),
    }
    _digest_cache[case_id] = digest
    return digest


def clear_digest_cache(case_id):
    """Forget the cached digest of a case, e.g. after re-ingesting it."""
    _digest_cache.pop(case_id, None)


def digest_markdown(digest):
    """Render a digest dict as markdown for the chat window."""
    lines = [f"**{digest['title']}** ({digest['gr_no']})"]
    for section in digest["sections"]:
        lines.append(f"\n### {section['heading']}")
        lines.extend(f"\n{p}" for p in section["paragraphs"])
    return "\n".join(lines)


def answer_follow_up(message, history, case_id):
    """Answer a question about one case from its most relevant excerpts.

    Return (answer, docs).
    """
    vector_store = store.get_vector_store()
    docs = vector_store.similarity_search(
        message,
        k=FOLLOW_UP_K,
        filter={"case_id": case_id, "section": EXCLUDE_NOTES},
    )
    docs += vector_store.similarity_search(
        message,
        k=FOLLOW_UP_DISPOSITIVE_K,
        filter={"case_id": case_id, "section": "dispositive"},
    )
    docs = unique_docs(docs)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", prompts.FOLLOW_UP_SYSTEM),
            MessagesPlaceholder("history"),
            ("human", prompts.FOLLOW_UP_USER),
        ]
    )
    llm = get_llm("answer", max_tokens=ANSWER_MAX_TOKENS)
    answer = (prompt | llm | StrOutputParser()).invoke(
        {
            "history": to_messages(history),
            "excerpts": format_excerpts(docs),
            "question": message,
        }
    )
    return answer, docs


def search_cases(message, case_limit=SEARCH_CASES,
                 per_case=EXCERPTS_PER_CASE):
    """Return the best excerpts for the case_limit closest cases.

    Search each case separately with the same query vector and rank the
    cases by their best score. One search over everything would let a
    long case (Oposa has 41 chunks) fill the results and hide the rest.
    Each item is a list of up to per_case documents.
    """
    vector_store = store.get_vector_store()
    vector = vector_store.embeddings.embed_query(message)
    scored = []
    for case_id in cases.load_cases():
        hits = vector_store.similarity_search_by_vector_with_score(
            vector,
            k=per_case,
            filter={"case_id": case_id, "section": EXCLUDE_NOTES},
        )
        if hits:
            scored.append((hits[0][1], [doc for doc, _ in hits]))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [group for _, group in scored[:case_limit]]


def answer_search(message, verify=False):
    """Find the cases that really match a question. Return (answer, docs).

    Take the closest cases from search_cases() and have the LLM read
    their excerpts and name the ones that truly match, so the decision
    rests on the text and not on similarity scores (which overlap too
    much between in-scope and out-of-scope questions to use as a cut-off).
    With verify=True, every case is checked with one excerpt each; this
    is used to double-check a decline. The answer is empty, and docs is
    empty, when nothing matches.
    """
    if verify:
        top = search_cases(
            message,
            case_limit=len(cases.load_cases()),
            per_case=VERIFY_EXCERPTS_PER_CASE,
        )
    else:
        top = search_cases(message)
    candidates = [
        f"## case_id: {group[0].metadata['case_id']} | "
        f"{group[0].metadata['title']} ({group[0].metadata['gr_no']})\n"
        f"{format_excerpts(group)}"
        for group in top
    ]
    prompt = ChatPromptTemplate.from_messages(
        [("system", prompts.SEARCH_SYSTEM), ("human", prompts.SEARCH_USER)]
    )
    result = invoke_structured(
        prompt,
        SearchResult,
        {"question": message, "candidates": "\n\n".join(candidates)},
        ANSWER_MAX_TOKENS,
    )
    by_case = {group[0].metadata["case_id"]: group for group in top}
    lines = []
    docs = []
    for match in result.matches:
        group = by_case.get(match.case_id)
        if group is None:
            continue
        meta = group[0].metadata
        lines.append(
            f"- **{meta['title']}** ({meta['gr_no']}): {match.reason}"
        )
        docs.extend(group)
    return "\n".join(lines), docs


def answer_general(message, history):
    """Define a legal term from general knowledge, with no retrieval."""
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", prompts.GENERAL_SYSTEM),
            MessagesPlaceholder("history"),
            ("human", "{question}"),
        ]
    )
    llm = get_llm("answer", max_tokens=ANSWER_MAX_TOKENS)
    return (prompt | llm | StrOutputParser()).invoke(
        {"history": to_messages(history), "question": message}
    )


def respond(message, history, active_case_id):
    """Route a chat message and return the /chat response dict.

    The dict has answer, intent, case_id and sources. "digest" and
    "follow_up" set case_id so the frontend can keep the case active.

    The router's "out_of_scope" is only a first guess made from short
    case cards. Before declining, it is checked against the indexed
    text with a search, so a question the cards miss (for example a
    party's first name) is still answered when the decisions do cover it.
    """
    intent = router.route(message, history, active_case_id)
    verify = intent.kind == "out_of_scope"
    if verify:
        intent = router.Intent(kind="search")
    case_id = None
    sources = []
    if intent.kind == "digest":
        digest = build_digest(intent.case_id)
        answer = digest_markdown(digest)
        sources = digest["sources"]
        case_id = intent.case_id
    elif intent.kind == "follow_up":
        answer, docs = answer_follow_up(message, history, intent.case_id)
        sources = to_sources(docs)
        case_id = intent.case_id
    elif intent.kind == "search":
        answer, docs = answer_search(message, verify=verify)
        sources = to_sources(docs)
        if not answer:
            answer = prompts.OUT_OF_SCOPE_REPLY.format(
                cases=cases.case_list_text()
            )
            intent = router.Intent(kind="out_of_scope")
    else:
        answer = answer_general(message, history)
    return {
        "answer": answer,
        "intent": intent.kind,
        "case_id": case_id,
        "sources": sources,
    }
