"""Fetch Supreme Court decisions and clean them into text for indexing."""

import re

import httpx
from bs4 import BeautifulSoup

USER_AGENT = "phlaw-rag/0.1"

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
    soup = BeautifulSoup(response.text, "html.parser")
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
