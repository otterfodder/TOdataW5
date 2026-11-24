"""Validate the bundled dashboard against fresh City of Toronto source queries."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from property_standards import fetch_property_data, normalize_property_standards
from wardwatch import fetch_features, normalize

PROJECT = Path(__file__).resolve().parents[1]
AIC_FIELDS = (
    "application_number", "type_description", "category", "status", "status_group",
    "submitted_date", "latest_milestone", "latest_milestone_date", "hearing_date",
    "community_meeting_date", "description", "planner", "planner_email", "planner_phone",
)
PROPERTY_FIELDS = (
    "application_number", "type_description", "status", "status_group", "submitted_date",
    "notice_or_order_date", "next_inspection", "expiry_date", "issue", "deficiencies",
)


def addresses(app: dict[str, Any]) -> list[str]:
    return sorted(item["address"] for item in app["addresses"])


def compare(current: list[dict[str, Any]], live: list[dict[str, Any]], fields: tuple[str, ...]) -> dict[str, Any]:
    current_by_id = {app["id"]: app for app in current}
    live_by_id = {app["id"]: app for app in live}
    missing_from_dashboard = sorted(set(live_by_id) - set(current_by_id))
    missing_from_live = sorted(set(current_by_id) - set(live_by_id))
    mismatches = []
    for app_id in sorted(set(current_by_id) & set(live_by_id)):
        before = current_by_id[app_id]
        after = live_by_id[app_id]
        for field in (*fields, "addresses"):
            expected = addresses(after) if field == "addresses" else after.get(field)
            actual = addresses(before) if field == "addresses" else before.get(field)
            if actual != expected:
                mismatches.append({"id": app_id, "field": field, "dashboard": actual, "live": expected})
    return {
        "dashboard_records": len(current_by_id),
        "live_records": len(live_by_id),
        "records_checked": len(set(current_by_id) & set(live_by_id)),
        "missing_from_dashboard": missing_from_dashboard[:50],
        "missing_from_live": missing_from_live[:50],
        "field_mismatch_count": len(mismatches),
        "field_mismatches": mismatches[:50],
        "passed": not missing_from_dashboard and not missing_from_live and not mismatches,
    }


def main() -> int:
    data = json.loads((PROJECT / "public/data/latest.json").read_text(encoding="utf-8"))
    current_aic = [app for app in data["applications"] if app["category"] != "property"]
    current_property = [app for app in data["applications"] if app["category"] == "property"]

    live_aic = normalize(fetch_features(data["ward"]["number"]))
    property_data = fetch_property_data(data["ward"]["number"])
    live_property, quality, _ = normalize_property_standards(property_data, data["ward"]["number"])

    aic_report = compare(current_aic, live_aic, AIC_FIELDS)
    property_report = compare(current_property, live_property, PROPERTY_FIELDS)
    aic_report["dashboard_open_by_category"] = dict(Counter(
        app["category"] for app in current_aic if app["status_group"].lower() == "open"
    ))
    aic_report["live_open_by_category"] = dict(Counter(
        app["category"] for app in live_aic if app["status_group"].lower() == "open"
    ))
    property_report["live_address_quality"] = quality
    report = {
        "validated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dashboard_snapshot": data["generated_at"],
        "method": "Fresh downloads from the official AIC ArcGIS layer and City CKAN resources; exact ID, address, status, date, contact, and deficiency comparisons.",
        "aic": aic_report,
        "property_standards": property_report,
        "passed": aic_report["passed"] and property_report["passed"],
    }
    output = PROJECT / "validation/live-source-validation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
