"""Fetch every case in data/cases.yaml into data/raw/<case_id>.txt.

Run from the backend directory:

    python -m scripts.fetch_all
"""

from pathlib import Path

import yaml

from app.ingest import fetch_clean

ROOT = Path(__file__).resolve().parents[1]


def main():
    """Fetch and save each case, then print a one-line check per file.

    The check reports the character count and whether the text contains
    "WHEREFORE" or "SO ORDERED", a sign the full decision was captured.
    """
    cases = yaml.safe_load((ROOT / "data" / "cases.yaml").read_text())
    for case in cases:
        text = fetch_clean(case["url"])
        path = ROOT / "data" / "raw" / f"{case['id']}.txt"
        path.write_text(text, encoding="utf-8")
        found = "WHEREFORE" in text or "SO ORDERED" in text
        print(
            f"{case['id']}: {len(text):>7} chars  "
            f"dispositive={'yes' if found else 'NO'}  "
            f"start={text[:40]!r}"
        )


if __name__ == "__main__":
    main()
