"""Point-in-time sector crowding export from authorised daily panels."""
import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from factors.calculate import StockDay, daily_factors, historical_midrank, trailing_mean

LOCAL = timezone(timedelta(hours=8))
METRICS = {"S": "ratio", "Q": "multiple", "D": "ratio", "U_plus": "ratio"}


def export(payload):
    sessions = payload["sessions"]
    if not sessions:
        raise ValueError("a trading calendar is required")
    dates = [item["date"] for item in sessions]
    calendar = [date.fromisoformat(value) for value in dates]
    if dates != [day.isoformat() for day in calendar] or calendar != sorted(set(calendar)):
        raise ValueError("sessions must be ordered unique ISO dates")
    sectors = payload["sectors"]
    if not sectors or any(not re.fullmatch("[a-z0-9_]{1,50}", key) for key in sectors):
        raise ValueError("sector IDs are required and must be stable ASCII keys")
    if len(set(sectors.values())) != len(sectors):
        raise ValueError("sector memberships must map to distinct labels")
    records = []
    history = {(sector, metric): [] for sector in sectors for metric in METRICS}
    smooth_history = {key: [] for key in history}
    previous_availability = None
    for session in sessions:
        observed = session["date"]
        rows = session.get("stocks")
        timestamp = session.get("available_at")
        if rows is not None:
            if not rows or not timestamp:
                raise ValueError("stock panels require rows and availability")
            available = datetime.fromisoformat(timestamp)
            if available.utcoffset() is None or available.astimezone(LOCAL).date().isoformat() < observed:
                raise ValueError("invalid availability timestamp")
            if previous_availability is not None and available < previous_availability:
                raise ValueError("availability must be nondecreasing across sessions")
            previous_availability = available
            stocks = [StockDay(**stock) for stock in rows]
        for key, label in sorted(sectors.items()):
            raw = daily_factors(stocks, label) if rows is not None else {}
            for metric, unit in METRICS.items():
                value = raw.get(metric)
                baseline = history[key, metric]
                # Five sessions, including the current date. Missing calendar slots are explicit.
                metric_key = metric.lower()
                records.append({
                    "family":"crowding","scope":key,"date":observed,"metric":metric_key,
                    "value":value,"unit":unit,"available_at":timestamp if rows is not None else None,
                    "state":"observed" if value is not None else "unobserved",
                    "method":"sector_panel_v1",
                })
                baseline.append(value)
                score = trailing_mean(baseline)
                ranks = smooth_history[key, metric]
                percentile = historical_midrank(score, ranks)
                ranks.append(score)
                records.append({
                    "family":"crowding","scope":key,"date":observed,"metric":metric_key+"_5d_percentile",
                    "value":percentile,"unit":"percentile_0_100","available_at":timestamp if rows is not None else None,
                    "state":"observed" if percentile is not None else "unobserved",
                    "method":"sector_panel_5d_252d_v1",
                })
    return {"version":1,"records":records}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    data = json.loads(a.input.read_text(encoding="utf-8-sig"))
    a.output.write_text(json.dumps(export(data), ensure_ascii=False, allow_nan=False, indent=2)+"\n", encoding="utf8")


if __name__ == "__main__":
    main()

