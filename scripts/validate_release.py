"""Validate the complete static release without contacting City services."""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_json(path: Path) -> Any:
    require(path.is_file() and path.stat().st_size > 0, f"Missing or empty file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    project = Path(__file__).resolve().parents[1]
    try:
        data = load_json(project / "public/data/latest.json")
        applications = data["applications"]
        require(isinstance(applications, list) and applications, "The register is empty.")
        require(data["ward"]["number"] == "05", "The release is not for Ward 05.")
        captured = datetime.fromisoformat(data["generated_at"])
        require(captured.tzinfo is not None, "The capture timestamp has no timezone.")

        ids = [str(app["id"]) for app in applications]
        require(len(ids) == len(set(ids)), "Duplicate record IDs were found.")
        categories = {app["category"] for app in applications}
        require(categories <= {"planning", "coa", "tlab", "property"}, "An unknown category was found.")
        require("property" in categories, "Property Standards records are missing.")
        require(categories - {"property"}, "AIC records are missing.")

        open_count = sum(app["status_group"].lower() == "open" for app in applications)
        stats = data["stats"]
        require(stats["applications"] == len(applications), "Total record statistics do not match.")
        require(stats["open"] == open_count, "Open record statistics do not match.")
        require(stats["closed"] == len(applications) - open_count, "Closed record statistics do not match.")
        property_count = sum(app["category"] == "property" for app in applications)
        require(stats["property_records"] == property_count, "Property Standards statistics do not match.")
        require(data["latest_digest"]["counts"]["applications"] == len(applications), "Digest statistics do not match.")

        state = load_json(project / "data/state/ward-05.json")
        require(state["captured_at"] == data["generated_at"], "Production state and dashboard timestamps differ.")
        require({str(app["id"]) for app in state["applications"]} == set(ids), "Production state and dashboard IDs differ.")

        script_path = project / "public/data/latest.js"
        require(script_path.is_file(), "The browser data script is missing.")
        script = script_path.read_text(encoding="utf-8")
        prefix = "window.__WARD5_DATA__="
        require(script.startswith(prefix) and script.endswith(";"), "The browser data script is malformed.")
        require(json.loads(script[len(prefix):-1]) == data, "Browser and JSON dashboard data differ.")

        csv_path = project / "public" / data["downloads"]["all_csv"]
        require(csv_path.is_file(), "The complete public CSV is missing.")
        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            csv_rows = list(csv.DictReader(handle))
        require(len(csv_rows) == len(applications), "The public CSV row count does not match the register.")

        for name in ("latest_digest_html", "latest_digest_json"):
            require((project / "public" / data["downloads"][name]).is_file(), f"Missing download: {name}")
        for digest in data["recent_digests"]:
            for extension in ("html", "json"):
                path = project / "public/digests" / f"{digest['digest_date']}.{extension}"
                require(path.is_file(), f"Missing published digest: {path.name}")

        dist_index = project / "dist/index.html"
        require(dist_index.is_file(), "The built dashboard is missing.")
        require("data/latest.js" in dist_index.read_text(encoding="utf-8"), "The build does not load its dashboard data.")
        require((project / "dist/data/latest.js").read_bytes() == script_path.read_bytes(), "The built data is stale.")

        print(
            f"Release valid: {len(applications)} records ({open_count} open), "
            f"{len(csv_rows)} CSV rows, {len(data['recent_digests'])} published digest dates."
        )
        print(f"Snapshot: {data['generated_at']}")
        return 0
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, OSError, RuntimeError) as exc:
        print(f"Release validation failed: {exc}", file=sys.stderr)
        print("Deployment must not replace the last good publication.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
