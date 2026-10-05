"""Run the evaluation questions through the chatbot and write results.

Run from the backend directory:

    python -m scripts.eval

Each question in eval/questions.json is sent to the same function the
/chat endpoint uses, so the whole pipeline (router, retrieval, LLM) is
tested. The script writes eval/results.md (the numbers) and
eval/answers.json (the full answers, to read and grade by hand).

The checks are mechanical: right intent, right case cited, expected
phrases present, declined when out of scope. They cannot tell whether
an answer is legally correct, so read answers.json too.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from groq import RateLimitError

from app import chains
from app.config import get_settings

EVAL_DIR = Path(__file__).resolve().parents[1] / "eval"
# Free-tier token limits reset within a minute, so wait and try again.
RETRY_WAIT_SECONDS = 45
MAX_ATTEMPTS = 3
# A short pause between questions keeps us under the per-minute limit.
PAUSE_SECONDS = 3


def ask(item):
    """Return chains.respond() for one question, retrying on rate limits.

    History arrives as plain dicts; the chains expect objects with
    .role and .content, as the API's request models provide.
    """
    history = [SimpleNamespace(**m) for m in item.get("history", [])]
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return chains.respond(
                item["question"], history, item.get("active_case_id")
            )
        except RateLimitError:
            if attempt == MAX_ATTEMPTS:
                raise
            print(f"  rate limited; waiting {RETRY_WAIT_SECONDS}s")
            time.sleep(RETRY_WAIT_SECONDS)


def find_problems(expect, result, decline_markers):
    """Compare a result with an item's expectations.

    Return a list of short problem descriptions; empty means it passed.
    Phrase matching ignores case.
    """
    problems = []
    answer = result["answer"].lower()
    if "intent" in expect and result["intent"] != expect["intent"]:
        problems.append(
            f"intent {result['intent']}, expected {expect['intent']}"
        )
    cited = {source["case_id"] for source in result["sources"]}
    for case_id in expect.get("source_case_ids", []):
        if case_id not in cited:
            problems.append(f"{case_id} not in sources")
    for group in expect.get("must_mention", []):
        if not any(phrase.lower() in answer for phrase in group):
            problems.append(f"missing one of {group}")
    if expect.get("decline") and not any(
        marker in answer for marker in decline_markers
    ):
        problems.append("no decline wording")
    for phrase in expect.get("none_of", []):
        if phrase.lower() in answer:
            problems.append(f"contains forbidden phrase {phrase!r}")
    return problems


def run_item(item, decline_markers):
    """Run one question and return its result row, including the answer."""
    started = time.time()
    try:
        result = ask(item)
        problems = find_problems(item["expect"], result, decline_markers)
    except Exception as error:
        result = {"answer": "", "intent": "error", "sources": []}
        problems = [f"{type(error).__name__}: {str(error)[:120]}"]
    return {
        "id": item["id"],
        "type": item["type"],
        "question": item["question"],
        "passed": not problems,
        "problems": problems,
        "intent": result["intent"],
        "cited": sorted({s["case_id"] for s in result["sources"]}),
        "seconds": round(time.time() - started, 1),
        "answer": result["answer"],
    }


def write_results(rows):
    """Write eval/results.md: a summary by type and a row per question."""
    settings = get_settings()
    kinds = list(dict.fromkeys(row["type"] for row in rows))
    lines = [
        "# Evaluation results",
        "",
        f"Run: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC  ",
        f"Answer model: `{settings.llm_model}`  ",
        f"Router model: `{settings.router_model}`",
        "",
        "## Summary",
        "",
        "| Type | Passed |",
        "|---|---|",
    ]
    for kind in kinds:
        group = [row for row in rows if row["type"] == kind]
        passed = sum(row["passed"] for row in group)
        lines.append(f"| {kind} | {passed}/{len(group)} |")
    total = sum(row["passed"] for row in rows)
    lines += [
        f"| **all** | **{total}/{len(rows)}** |",
        "",
        "## Questions",
        "",
        "| Id | Result | Intent | Cited | Seconds | Problems |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['id']} | {'pass' if row['passed'] else 'FAIL'} "
            f"| {row['intent']} | {', '.join(row['cited']) or '-'} "
            f"| {row['seconds']} | {'; '.join(row['problems']) or '-'} |"
        )
    (EVAL_DIR / "results.md").write_text("\n".join(lines) + "\n")


def main():
    """Run every question, print progress and write both output files."""
    spec = json.loads((EVAL_DIR / "questions.json").read_text())
    markers = [m.lower() for m in spec["decline_markers"]]
    rows = []
    for item in spec["questions"]:
        row = run_item(item, markers)
        rows.append(row)
        status = "pass" if row["passed"] else "FAIL"
        print(f"{status}  {row['id']}  {row['problems'] or ''}")
        time.sleep(PAUSE_SECONDS)
    write_results(rows)
    (EVAL_DIR / "answers.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False) + "\n"
    )
    print(f"{sum(r['passed'] for r in rows)}/{len(rows)} passed")


if __name__ == "__main__":
    main()
