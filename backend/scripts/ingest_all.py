"""Fetch, chunk and index every case in data/cases.yaml.

Run from the backend directory:

    python -m scripts.ingest_all --fetch      # download texts, then index
    python -m scripts.ingest_all              # index the saved texts
    python -m scripts.ingest_all --dry-run    # chunk only, no Pinecone
"""

import argparse
from collections import Counter
from pathlib import Path

import yaml

from app.ingest import chunk_decision, fetch_clean, index_case

ROOT = Path(__file__).resolve().parents[1]


def parse_args():
    """Parse the command-line flags."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="download each decision and overwrite data/raw first",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="chunk the texts and print a summary without using Pinecone",
    )
    return parser.parse_args()


def load_text(case, fetch):
    """Return the decision text, downloading and saving it if asked.

    Without fetch, read the saved copy in data/raw/<case_id>.txt.
    """
    path = ROOT / "data" / "raw" / f"{case['id']}.txt"
    if fetch:
        path.write_text(fetch_clean(case["url"]), encoding="utf-8")
    return path.read_text(encoding="utf-8")


def main():
    """Process every case and print one summary line for each.

    The line shows the character count, whether the dispositive text
    ("WHEREFORE" or "SO ORDERED") is present, and the chunk count. A
    dry run also lists how many chunks fall in each section.
    """
    args = parse_args()
    cases = yaml.safe_load((ROOT / "data" / "cases.yaml").read_text())
    for case in cases:
        text = load_text(case, args.fetch)
        found = "WHEREFORE" in text or "SO ORDERED" in text
        line = (
            f"{case['id']}: {len(text):>7} chars  "
            f"dispositive={'yes' if found else 'NO'}"
        )
        if args.dry_run:
            docs = chunk_decision(text, case)
            sections = Counter(d.metadata["section"] for d in docs)
            print(f"{line}  chunks={len(docs)}  {dict(sections)}")
        else:
            print(f"{line}  indexed={index_case(case, text)} chunks")


if __name__ == "__main__":
    main()
