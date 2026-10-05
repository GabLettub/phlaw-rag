"""The six indexed cases: metadata, cards, and name matching."""

import re
from functools import lru_cache
from pathlib import Path

import yaml

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# "G.R. No. 101083", "GR 101083", "G.R. Nos. 171947-48" -> the first number.
GR_NUMBER_RE = re.compile(r"G\.?\s?R\.?\s*(?:Nos?\.?)?\s*(\d{5,6})", re.I)


@lru_cache
def load_cases():
    """Return every case as a dict, keyed by case_id, in file order.

    Merge data/cases.yaml (the facts used for ingestion) with
    data/cards.json (the short summary and the name aliases). The date
    is converted to an ISO string so it can be sent as JSON.
    """
    raw = yaml.safe_load((DATA_DIR / "cases.yaml").read_text())
    cards = yaml.safe_load((DATA_DIR / "cards.json").read_text())
    cases = {}
    for case in raw:
        card = cards.get(case["id"], {})
        cases[case["id"]] = {
            "case_id": case["id"],
            "title": case["title"],
            "gr_no": case["gr_no"],
            "date": str(case["date"]),
            "topic": case["topic"],
            "url": case["url"],
            "summary": card.get("summary", ""),
            "aliases": card.get("aliases", []),
        }
    return cases


def get_case(case_id):
    """Return one case dict, or None if the id is unknown."""
    return load_cases().get(case_id)


def match_case(message):
    """Return the case_id a message names by G.R. number or name.

    Check for a G.R. number first, then for any alias (case-insensitive
    substring). Return None when the message names no known case.
    """
    for number in GR_NUMBER_RE.findall(message):
        case_id = f"gr-{number}"
        if case_id in load_cases():
            return case_id
    lowered = message.lower()
    for case in load_cases().values():
        if any(alias in lowered for alias in case["aliases"]):
            return case["case_id"]
    return None


def case_list_text():
    """Return a bullet list of the cases for use in prompts and replies."""
    return "\n".join(
        f"- {c['title']} ({c['gr_no']}, {c['date'][:4]}): {c['topic']}"
        for c in load_cases().values()
    )


def case_cards_text():
    """Return each case with its topic and summary, for the router prompt.

    The router needs more than titles to tell that a question about,
    say, electronic evidence belongs to one of the indexed cases.
    """
    return "\n".join(
        f"- {c['case_id']}: {c['title']} ({c['gr_no']}). "
        f"Topic: {c['topic']}. {c['summary']} "
        f"Also known as / parties: {', '.join(c['aliases'])}."
        for c in load_cases().values()
    )
