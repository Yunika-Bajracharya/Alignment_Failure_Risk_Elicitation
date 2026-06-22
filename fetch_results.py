#!/usr/bin/env python3
"""Pull workshop results from Supabase into a tidy long-format CSV.

Hits the Supabase REST (PostgREST) API directly with `requests`, so there is no
`supabase` package to install. Joins `elicitation_runs` to `experts` so each row
is one assessment (person x round x failure-mode x technique) with the expert
profile attached.

Usage:
    python fetch_results.py                 # writes results.csv next to this file
    python fetch_results.py out.csv         # custom output path
    python fetch_results.py --since 2026-06-23T15:45   # custom cutoff (no offset = CEST)
    python fetch_results.py --all           # no date filter (include everything)

By default only entries on/after 23 June 2026, 15:45 CEST (Brussels) are kept,
to exclude pre-workshop test data. Override with --since, or disable with --all.

Credentials are read from the environment or a `.env` file in this folder:
    SUPABASE_URL=https://YOUR-PROJECT.supabase.co
    SUPABASE_KEY=YOUR-SERVICE-ROLE-KEY

Use the service_role key (Settings -> API): it bypasses Row-Level Security so
SELECT reliably returns all rows. It is secret -- local use only, never the
browser. (.env is gitignored.) The anon/publishable key also works only if the
tables have a SELECT policy; otherwise an insert-only table returns 0 rows.
"""

import argparse
import csv
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent

# Default cutoff: 23 June 2026, 15:45 CEST (Europe/Brussels, UTC+2) == 13:45 UTC.
CEST = timezone(timedelta(hours=2))
DEFAULT_SINCE = datetime(2026, 6, 23, 15, 45, tzinfo=CEST)

# Long-format output columns (assessment grain, expert profile joined in).
COLUMNS = [
    "personal_id", "round", "group_id", "affiliation", "role", "years_experience",
    "failure_mode_id", "technique_id", "point_estimate", "lower_bound",
    "upper_bound", "confidence", "rationale", "created_at",
]
PAGE_SIZE = 1000  # PostgREST default max page; we paginate to be safe.


def load_dotenv(path: Path) -> None:
    """Minimal .env loader (no python-dotenv dependency)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


def get_credentials() -> tuple[str, str]:
    load_dotenv(HERE / ".env")
    url = os.environ.get("SUPABASE_URL") or os.environ.get("VITE_SUPABASE_PROJECT_URL")
    key = (
        os.environ.get("SUPABASE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("VITE_PUBLISHABLE_API_KEY")
    )
    if not url or not key:
        sys.exit(
            "Missing credentials. Set SUPABASE_URL and SUPABASE_KEY in the "
            "environment or in a .env file next to this script."
        )
    return url.rstrip("/"), key


def fetch_table(base_url: str, key: str, table: str) -> list[dict]:
    """Fetch all rows from a table via PostgREST, paginating on offset."""
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    rows: list[dict] = []
    offset = 0
    while True:
        resp = requests.get(
            f"{base_url}/rest/v1/{table}",
            headers=headers,
            params={"select": "*", "limit": PAGE_SIZE, "offset": offset},
            timeout=30,
        )
        if resp.status_code != 200:
            # PostgREST returns a JSON {message, hint, ...} on error.
            sys.exit(f"Error reading '{table}' (HTTP {resp.status_code}): {resp.text}")
        batch = resp.json()
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def join_rows(experts: list[dict], runs: list[dict]) -> list[dict]:
    by_id = {e.get("id"): e for e in experts}
    out = []
    for r in runs:
        e = by_id.get(r.get("expert_id"), {})
        out.append({
            "personal_id": r.get("personal_id") or e.get("personal_id") or "",
            "round": r.get("round") if r.get("round") is not None else e.get("round", ""),
            "group_id": r.get("group_id") if r.get("group_id") is not None else e.get("group_id", ""),
            "affiliation": e.get("affiliation", ""),
            "role": e.get("role", ""),
            "years_experience": e.get("years_experience", ""),
            "failure_mode_id": r.get("failure_mode_id", ""),
            "technique_id": r.get("technique_id", ""),
            "point_estimate": r.get("point_estimate", ""),
            "lower_bound": r.get("lower_bound", ""),
            "upper_bound": r.get("upper_bound", ""),
            "confidence": r.get("confidence", ""),
            "rationale": r.get("rationale", ""),
            "created_at": e.get("created_at") or r.get("created_at") or "",
        })
    return out


def parse_dt(s: str, assume_tz=CEST) -> datetime:
    """Parse an ISO-8601 datetime; attach `assume_tz` if it carries no offset."""
    dt = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=assume_tz)


def filter_since(rows: list[dict], cutoff: datetime) -> tuple[list[dict], int]:
    """Keep rows whose created_at is on/after cutoff; drop missing/unparseable ones."""
    kept, dropped = [], 0
    for row in rows:
        raw = row.get("created_at")
        try:
            dt = parse_dt(raw, assume_tz=timezone.utc) if raw else None
        except ValueError:
            dt = None
        if dt is not None and dt >= cutoff:
            kept.append(row)
        else:
            dropped += 1
    return kept, dropped


def main() -> None:
    ap = argparse.ArgumentParser(description="Pull workshop results from Supabase into a CSV.")
    ap.add_argument("out", nargs="?", default=str(HERE / "results.csv"),
                    help="output CSV path (default: results.csv next to this script)")
    ap.add_argument("--since", default=None,
                    help="only include entries on/after this datetime (ISO 8601; no offset = "
                         "CEST). Default: 2026-06-23 15:45 CEST.")
    ap.add_argument("--all", action="store_true",
                    help="include all entries (disable the date filter)")
    args = ap.parse_args()

    if args.all:
        cutoff = None
    elif args.since:
        try:
            cutoff = parse_dt(args.since)
        except ValueError:
            sys.exit(f"Could not parse --since {args.since!r}; use ISO 8601, e.g. 2026-06-23T15:45")
    else:
        cutoff = DEFAULT_SINCE

    base_url, key = get_credentials()

    experts = fetch_table(base_url, key, "experts")
    runs = fetch_table(base_url, key, "elicitation_runs")
    print(f"experts:          {len(experts)} rows")
    print(f"elicitation_runs: {len(runs)} rows")

    if not experts and not runs:
        print(
            "\n! Both tables came back empty. If you know there is data, this is "
            "almost\n  certainly Row-Level Security blocking SELECT with this key. "
            "Use the\n  service_role key (Settings -> API) or add a SELECT policy.",
            file=sys.stderr,
        )

    joined = join_rows(experts, runs)

    if cutoff is None:
        print("date filter:      OFF (--all) — including all rows")
    else:
        joined, dropped = filter_since(joined, cutoff)
        print(f"date filter:      on/after {cutoff.isoformat()} "
              f"(= {cutoff.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}); "
              f"dropped {dropped} earlier/undated row(s)")

    out_path = Path(args.out).expanduser()
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(joined)

    print(f"\nWrote {len(joined)} assessment rows -> {out_path}")


if __name__ == "__main__":
    main()
