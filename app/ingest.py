"""Fetch Supreme Court decisions and clean them into text for indexing."""

import bisect
import re

import httpx
from bs4 import BeautifulSoup
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app import store

USER_AGENT = "phlaw-rag/0.1"

# About 375 tokens per chunk, under the roughly 500-token input limit
# of multilingual-e5-large.
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200

# Matches a heading line such as "SEPARATE OPINION" or "CONCURRING AND
# DISSENTING OPINION". Separate opinions come after the main decision
# and would pollute retrieval. The heading must sit on a short line, so
# sentences like "The Dissenting Opinion claims..." inside a long
# paragraph of the decision do not match.
_KIND = r"(?:SEPARATE|DISSENTING|CONCURRING)"
OPINION_RE = re.compile(
    rf"^[^\n]{{0,40}}{_KIND}(?: AND {_KIND})? OPINION[^\n]{{0,40}}$",
    re.MULTILINE | re.IGNORECASE,
)

# The caption is where the decision proper begins. Prefer the division
# line; fall back to the "G.R. No." line when there is none.
DIVISION_RE = re.compile(r"EN BANC|(?:FIRST|SECOND|THIRD) DIVISION")
GR_RE = re.compile(r"G\.R\. Nos?\.")

# Short heading lines that open a section of a decision. Each pattern
# must match the whole line. Headings vary between decisions, so these
# cover the ones seen in the six indexed cases.
SECTION_HEADINGS = {
    "facts": re.compile(
        r"(?:the )?(?:antecedent )?facts(?: and the case)?:?",
        re.IGNORECASE,
    ),
    "issues": re.compile(
        r"(?:the )?issues?(?: presented)?:?",
        re.IGNORECASE,
    ),
    "ruling": re.compile(
        r"(?:the |our )?(?:court.s )?rulings?(?: of the court)?:?",
        re.IGNORECASE,
    ),
}
HEADING_LINE_RE = re.compile(r"^[^\n]{1,40}$", re.MULTILINE)
WHEREFORE_RE = re.compile(r"^WHEREFORE", re.MULTILINE)
SO_ORDERED_RE = re.compile(r"SO ORDERED\.?")


def decode_page(content):
    """Decode page bytes as UTF-8, falling back to Windows-1252.

    Lawphil serves Windows-1252 pages without declaring it in the HTTP
    headers, so letting httpx guess turns curly quotes and dashes into
    replacement characters. Windows-1252 bytes are rarely valid UTF-8,
    so trying UTF-8 first is a safe test.
    """
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("cp1252", errors="replace")


def normalize_text(text):
    """Tidy raw page text into clean paragraphs.

    Replace non-breaking spaces and Windows line endings with plain
    ones, collapse runs of spaces, and join lines that were hard-wrapped
    mid-sentence. Blank lines are kept as paragraph breaks.
    """
    text = text.replace("\xa0", " ").replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    # Join hard-wrapped lines but keep blank-line paragraph breaks.
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip()


def fetch_clean(url):
    """Download a decision page and return only the main decision text.

    Fetch the page, strip scripts, navigation and footers, and flatten
    it to text with paragraph breaks preserved. Then trim the text to
    start at the caption and to end before the first separate,
    concurring or dissenting opinion heading.
    """
    response = httpx.get(
        url,
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    soup = BeautifulSoup(decode_page(response.content), "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "head"]):
        tag.decompose()
    # Block boundaries become newlines so paragraphs survive get_text().
    for line_break in soup.find_all("br"):
        line_break.replace_with("\n")
    for block in soup.find_all(["p", "blockquote", "div", "tr"]):
        block.append("\n\n")
    text = normalize_text(soup.get_text())

    caption = DIVISION_RE.search(text) or GR_RE.search(text)
    if caption:
        text = text[caption.start():]
    opinion = OPINION_RE.search(text)
    if opinion:
        text = text[:opinion.start()].rstrip()
    return text


def section_markers(text):
    """Return sorted (offset, section) pairs marking where sections begin.

    A section starts at a short heading line that matches
    SECTION_HEADINGS. The dispositive section starts at the last
    paragraph beginning with "WHEREFORE". The "notes" section (the
    signature block and footnotes) starts right after the "SO ORDERED"
    that closes it. Text before the first marker is "body", which is
    also what section_at() returns for it.
    """
    markers = []
    for line in HEADING_LINE_RE.finditer(text):
        for section, pattern in SECTION_HEADINGS.items():
            if pattern.fullmatch(line.group().strip()):
                markers.append((line.start(), section))
    wherefores = list(WHEREFORE_RE.finditer(text))
    if wherefores:
        start = wherefores[-1].start()
        markers.append((start, "dispositive"))
        closing = SO_ORDERED_RE.search(text, start)
        if closing:
            markers.append((closing.end(), "notes"))
    return sorted(markers)


def section_at(markers, offset):
    """Return the section that contains the character at offset."""
    position = bisect.bisect_right(markers, (offset, "\uffff"))
    return markers[position - 1][1] if position else "body"


def chunk_decision(text, case):
    """Split one decision into LangChain Documents ready to index.

    Each chunk carries the case metadata (case_id, title, gr_no, date,
    topic, url), its chunk_index and its section. The page_content is
    stored by Pinecone as the "text" field.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        add_start_index=True,
    )
    base = {
        "case_id": case["id"],
        "title": case["title"],
        "gr_no": case["gr_no"],
        "date": str(case["date"]),
        "topic": case["topic"],
        "url": case["url"],
    }
    docs = splitter.create_documents([text], metadatas=[base])
    markers = section_markers(text)
    for index, doc in enumerate(docs):
        doc.metadata["chunk_index"] = index
        doc.metadata["section"] = section_at(
            markers, doc.metadata["start_index"]
        )
    return docs


def index_case(case, text):
    """Replace one case's chunks in Pinecone and return the chunk count.

    Delete the case's old chunks first, then upsert the new ones under
    stable ids ("<case_id>-<chunk_index>"). Running it twice therefore
    gives the same index, which keeps re-runs from n8n safe.
    """
    docs = chunk_decision(text, case)
    store.delete_case(case["id"])
    ids = [f"{case['id']}-{d.metadata['chunk_index']}" for d in docs]
    store.get_vector_store().add_documents(docs, ids=ids)
    return len(docs)
