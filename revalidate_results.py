import json
import re
from pathlib import Path

source = Path("results_backup.jsonl")
target = Path("results_corrected.jsonl")

def get_body(briefing):
    text = briefing or ""
    # Remove the Sources section, not the first divider between briefing sections.
    match = re.search(
        r"\n\s*---\s*\n\s*(?:📚\s*)?\*\*Sources:\*\*",
        text,
        flags=re.IGNORECASE
    )
    return text[:match.start()].strip() if match else text.strip()

records = []
with source.open("r", encoding="utf-8") as f:
    for line_no, line in enumerate(f, start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON on line {line_no}: {e}")

        if not record.get("scenario") and record.get("scenaario"):
            record["scenario"] = record["scenaario"]

        body = get_body(record.get("briefing", ""))
        words = len(body.split())
        has_takeaway = bool(re.search(r"takeaway", body, re.IGNORECASE))

        record["words"] = words
        record["under_400"] = words <= 400
        record["has_takeaway"] = has_takeaway
        record["ok"] = (
            not record.get("error")
            and bool(body)
            and not body.startswith("No news found")
            and has_takeaway
            and words <= 400
        )
        records.append(record)

with target.open("w", encoding="utf-8") as f:
    for record in records:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

print(f"Records processed: {len(records)}")
print(f"Corrected dataset: {target}")
print(f"Missing scenarios: {sum(not r.get('scenario') for r in records)}")
print(f"Successful under corrected validation: {sum(bool(r.get('ok')) for r in records)}")
