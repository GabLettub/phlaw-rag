"""Intent routing: a regex fast path, then an LLM with structured output."""

import logging
import re
from typing import Literal, Optional

from groq import BadRequestError
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from app import cases, prompts
from app.llm import get_llm

# Words that signal the user wants a whole-case summary rather than an
# answer to one question about it.
DIGEST_HINT_RE = re.compile(
    r"\b(digest|summar\w*|brief|overview|tell me about)\b", re.I
)
# A bare case name ("Oposa v. Factoran") with no question is read as a
# request for the digest.
NAME_ONLY_MAX_WORDS = 10
ROUTER_MAX_TOKENS = 1024
# With a case open, wording like "the Court", "the ruling" or "held"
# almost always refers to that case, so the LLM is not needed.
FOLLOW_UP_HINT_RE = re.compile(
    r"\b(the court|the decision|the ruling|the case|held|petitioners?|"
    r"respondents?|justice|the justices)\b",
    re.I,
)
# At low reasoning effort the router model often replies in prose
# instead of JSON on short messages, which Groq reports as a 400. A
# retry at medium effort fixes it, so low stays the cheap default.
RETRY_EFFORT = "medium"

logger = logging.getLogger("phlaw")


class Intent(BaseModel):
    """The router's decision: what the user wants and about which case."""

    kind: Literal["digest", "follow_up", "search", "general", "out_of_scope"]
    case_id: Optional[str] = None


def route_by_regex(message):
    """Return an Intent if the message names a case, else None.

    A G.R. number or known case name is an obvious signal, so no LLM
    call is needed. The intent is "digest" when the message asks for a
    summary or is only a case name; otherwise it is a question about
    that case, so "follow_up".
    """
    case_id = cases.match_case(message)
    if case_id is None:
        return None
    is_name_only = (
        "?" not in message and len(message.split()) <= NAME_ONLY_MAX_WORDS
    )
    if DIGEST_HINT_RE.search(message) or is_name_only:
        return Intent(kind="digest", case_id=case_id)
    return Intent(kind="follow_up", case_id=case_id)


def route_by_llm(message, history, active_case_id):
    """Ask the small router model to classify the message.

    The last two history messages and the active case are included so
    short references like "why?" can be resolved. If the model does not
    produce valid JSON even at RETRY_EFFORT, fall back to a "search",
    which is grounded in the indexed text and so safe.
    """
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", prompts.ROUTER_SYSTEM),
            ("human", "Recent messages:\n{recent}\n\nLatest: {message}"),
        ]
    )
    recent = "\n".join(f"{m.role}: {m.content[:300]}" for m in history[-2:])
    variables = {
        "cases": cases.case_cards_text(),
        "active": active_case_id or "none",
        "ids": ", ".join(cases.load_cases()),
        "recent": recent or "(none)",
        "message": message,
    }
    for effort in (None, RETRY_EFFORT):
        llm = get_llm("router", max_tokens=ROUTER_MAX_TOKENS, effort=effort)
        # json_schema mode avoids a Groq error where the model calls the
        # function-calling tool by the wrong name (intent vs Intent).
        structured = llm.with_structured_output(Intent, method="json_schema")
        try:
            return (prompt | structured).invoke(variables)
        except BadRequestError as exc:
            logger.warning("Router output not parseable: %s", exc)
    return Intent(kind="search")


def route(message, history, active_case_id):
    """Return a validated Intent for the message.

    Try the regex fast path, then the active-case hint, then the LLM.
    Afterwards repair the result
    so the chains can trust it: an unknown case_id is dropped, a
    follow_up with no case falls back to the active case, and a
    follow_up or digest that still has no case becomes a search.
    """
    # The id comes from the client, so ignore anything that is not an
    # indexed case (Swagger's default example sends the text "string").
    if active_case_id not in cases.load_cases():
        active_case_id = None
    intent = route_by_regex(message)
    if intent is None and active_case_id and FOLLOW_UP_HINT_RE.search(message):
        intent = Intent(kind="follow_up", case_id=active_case_id)
    if intent is None:
        intent = route_by_llm(message, history, active_case_id)
    if intent.case_id not in cases.load_cases():
        intent.case_id = None
    if intent.kind == "follow_up" and intent.case_id is None:
        intent.case_id = active_case_id
    if intent.kind in ("follow_up", "digest") and intent.case_id is None:
        intent.kind = "search"
    return intent
