"""City of Toronto Property Standards ingestion and Ward address matching.

Only official City open-data resources are used. Investigation addresses are
matched to the City's One Address Repository, whose address points include the
current municipal ward. No geocoding service, credentials, or third-party
packages are required.
"""
from __future__ import annotations

import csv
import io
import json
import re
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

CKAN_API = "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/"
CKAN_DUMP = "https://ckan0.cf.opendata.inter.prod-toronto.ca/datastore/dump/"
PACKAGE_URL = "https://open.toronto.ca/dataset/municipal-licensing-and-standards-investigation-activity/"
INFORMATION_URL = "https://secure.toronto.ca/InvestigationActivity/setup.do?action=init"
ADDRESS_POINTS_URL = "https://open.toronto.ca/dataset/address-points-municipal-toronto-one-address-repository/"
INVESTIGATIONS_RESOURCE = "fbaaf87a-558d-4437-95b3-7d8a6c6db7eb"
ADDRESSES_RESOURCE = "977671c0-b3c8-4dee-8305-2a688a5756ad"
DEFICIENCIES_RESOURCE = "47b74562-e799-4f0d-bdd4-e2ce17af5240"
ADDRESS_POINTS_RESOURCE = "0b3756af-9caf-4f0f-ac28-9c6617adede4"
INCLUDED_TYPES = (
    "Property Standards",
    "Order Issued Property Standards",
    "Notice Issued Prop Standards",
)
USER_AGENT = "Ward5DevelopmentWatch/2.0 (civic open-data reader)"


def clean(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def normalized(value: Any) -> str:
    text = (clean(value) or "").upper()
    if text == "NONE":
        return ""
    return re.sub(r"[^A-Z0-9]", "", text)


def source_date(value: Any) -> str | None:
    text = clean(value)
    if not text or text.upper() in {"N/A", "NONE", "NULL"}:
        return None
    for pattern in ("%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            pass
    return None


def request_json(url: str, retries: int = 3) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = json.load(response)
            if not payload.get("success", True):
                raise RuntimeError(f"City datastore returned an error: {payload}")
            return payload
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("City datastore request failed")


def fetch_csv_resource(resource_id: str, retries: int = 3) -> list[dict[str, Any]]:
    url = CKAN_DUMP + resource_id
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=240) as response:
                text = io.TextIOWrapper(response, encoding="utf-8-sig", newline="")
                rows = list(csv.DictReader(text))
            if not rows or "INVESTIGATION_ID" not in rows[0]:
                raise RuntimeError(f"City resource {resource_id} returned no usable rows")
            return rows
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError(f"City resource {resource_id} could not be read")


def fetch_ward_address_points(ward: str) -> list[dict[str, Any]]:
    """Fetch only the selected ward's canonical addresses, concurrently by page."""
    base = CKAN_API + "datastore_search?"

    def page(offset: int) -> dict[str, Any]:
        params = {
            "resource_id": ADDRESS_POINTS_RESOURCE,
            "limit": 5000,
            "offset": offset,
            "filters": json.dumps({"WARD": ward}),
        }
        return request_json(base + urllib.parse.urlencode(params))["result"]

    first = page(0)
    total = int(first["total"])
    batches = [first["records"]]
    with ThreadPoolExecutor(max_workers=4) as executor:
        for result in executor.map(page, range(5000, total, 5000)):
            batches.append(result["records"])
    rows = [row for batch in batches for row in batch]
    if len(rows) != total:
        raise RuntimeError(f"Address repository returned {len(rows)} of {total} Ward {ward} rows")
    return rows


def fetch_property_data(ward: str) -> dict[str, list[dict[str, Any]]]:
    """Fetch all four inputs before replacing any existing dashboard data."""
    with ThreadPoolExecutor(max_workers=4) as executor:
        investigations_future = executor.submit(fetch_csv_resource, INVESTIGATIONS_RESOURCE)
        addresses_future = executor.submit(fetch_csv_resource, ADDRESSES_RESOURCE)
        deficiencies_future = executor.submit(fetch_csv_resource, DEFICIENCIES_RESOURCE)
        points_future = executor.submit(fetch_ward_address_points, ward)
        return {
            "investigations": investigations_future.result(),
            "addresses": addresses_future.result(),
            "deficiencies": deficiencies_future.result(),
            "address_points": points_future.result(),
        }


def load_property_data(directory: Path) -> dict[str, list[dict[str, Any]]]:
    """Load a saved source set for reproducible tests or offline refreshes."""
    data: dict[str, list[dict[str, Any]]] = {}
    for name in ("investigations", "addresses", "deficiencies", "address_points"):
        csv_path = directory / f"{name}.csv"
        json_path = directory / f"{name}.json"
        if csv_path.exists():
            with csv_path.open(encoding="utf-8-sig", newline="") as handle:
                data[name] = list(csv.DictReader(handle))
        elif json_path.exists():
            data[name] = json.loads(json_path.read_text(encoding="utf-8"))
        else:
            raise FileNotFoundError(f"Missing Property Standards input: {name}.csv or {name}.json")
    return data


def point_coordinates(point: dict[str, Any]) -> tuple[float | None, float | None]:
    try:
        geometry = point.get("geometry")
        if isinstance(geometry, str):
            geometry = json.loads(geometry)
        longitude, latitude = geometry["coordinates"][:2]
        return float(latitude), float(longitude)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None, None


def normalize_property_standards(
    data: dict[str, list[dict[str, Any]]], ward: str
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Join investigations, addresses, and deficiencies for one municipal ward."""
    investigations = {
        str(row["INVESTIGATION_ID"]): row
        for row in data["investigations"]
        if clean(row.get("INVESTIGATION_TYPE")) in INCLUDED_TYPES and row.get("INVESTIGATION_ID")
    }
    if not investigations:
        raise RuntimeError("No Property Standards investigations were found; preserving previous data")

    exact: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    fallback: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for point in data["address_points"]:
        if clean(point.get("WARD")) != ward:
            continue
        key = (
            normalized(point.get("ADDRESS_NUMBER")),
            normalized(point.get("LINEAR_NAME")),
            normalized(point.get("LINEAR_NAME_TYPE")),
            normalized(point.get("LINEAR_NAME_DIR")),
        )
        if key[0] and key[1]:
            exact[key].append(point)
            fallback[key[:2]].append(point)

    matched: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    ambiguous_rows: list[dict[str, Any]] = []
    relevant_address_rows = 0
    for address in data["addresses"]:
        investigation_id = str(address.get("INVESTIGATION_ID") or "")
        if investigation_id not in investigations:
            continue
        relevant_address_rows += 1
        key = (
            normalized(address.get("PROPHOUSE")),
            normalized(address.get("PROPSTREET")),
            normalized(address.get("PROPSTREETTYPE")),
            normalized(address.get("PROPSTREETDIRECTION")),
        )
        candidates = exact.get(key) or fallback.get(key[:2], [])
        # Multiple points for one civic address are valid. Different candidate
        # addresses are ambiguous and must not be guessed into the ward.
        canonical_addresses = {normalized(point.get("ADDRESS_FULL")) for point in candidates}
        if len(canonical_addresses) != 1:
            if len(canonical_addresses) > 1:
                ambiguous_rows.append(address)
            continue
        point = candidates[0]
        latitude, longitude = point_coordinates(point)
        display = clean(address.get("ASSESSED_OR_MAILING_ADDRESS")) or clean(point.get("ADDRESS_FULL"))
        if not display:
            continue
        matched[investigation_id][display] = {
            "address": display,
            "canonical_address": clean(point.get("ADDRESS_FULL")),
            "latitude": latitude,
            "longitude": longitude,
        }

    deficiencies: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in data["deficiencies"]:
        investigation_id = str(row.get("INVESTIGATION_ID") or "")
        if investigation_id not in matched:
            continue
        item = {
            "location": clean(row.get("LOCATION")),
            "sublocation": clean(row.get("SUBLOCATION")),
            "text": clean(row.get("TEXT")),
            "status": clean(row.get("STATUS")),
        }
        if any(item.values()):
            deficiencies[investigation_id].append(item)

    applications = []
    for investigation_id, addresses in matched.items():
        row = investigations[investigation_id]
        address_list = sorted(addresses.values(), key=lambda item: item["address"])
        deficiency_list = sorted(
            deficiencies.get(investigation_id, []),
            key=lambda item: (item["location"] or "", item["sublocation"] or "", item["text"] or ""),
        )
        status = clean(row.get("CURRENT_STATUS")) or "Not supplied"
        issue = clean(row.get("ISSUE"))
        notice_date = source_date(row.get("NOTICE_OR_ORDER_DATE"))
        next_inspection = source_date(row.get("NEXT_INSPECTION"))
        applications.append({
            "id": f"property:{investigation_id}",
            "investigation_id": investigation_id,
            "application_number": clean(row.get("INVESTIGATION#")) or f"Investigation {investigation_id}",
            "reference_file": None,
            "folder_name": None,
            "folder_type": "PRS",
            "type_description": clean(row.get("INVESTIGATION_TYPE")) or "Property Standards",
            "investigation_type": clean(row.get("INVESTIGATION_TYPE")),
            "category": "property",
            "category_label": "Property Standards",
            "status": status,
            "status_group": "Closed" if status.lower().startswith("closed") else "Open",
            "record_status": status,
            "submitted_date": source_date(row.get("IN_DATE")),
            "completed_date": None,
            "latest_milestone": "Notice / order issued" if notice_date else None,
            "latest_milestone_date": notice_date,
            "hearing_date": None,
            "community_meeting_date": None,
            "last_modified_date": None,
            "description": issue or "Property Standards investigation",
            "issue": issue,
            "notice_or_order_date": notice_date,
            "next_inspection": next_inspection,
            "expiry_date": source_date(row.get("EXPIRY_DATE")),
            "deficiencies": deficiency_list,
            "deficiency_summary": " | ".join(
                " — ".join(filter(None, (item["location"], item["sublocation"], item["text"], item["status"])))
                for item in deficiency_list
            ) or None,
            "planner": None,
            "planner_email": None,
            "planner_phone": None,
            "aic_url": None,
            "source_url": INFORMATION_URL,
            "ward_number": ward,
            "ward_name": clean(address_list[0].get("ward_name")) or ("York South-Weston" if ward == "05" else f"Ward {ward}"),
            "addresses": address_list,
            "display_address": address_list[0]["address"],
        })

    applications.sort(key=lambda app: (app["submitted_date"] or "", app["application_number"]), reverse=True)
    if not applications:
        raise RuntimeError(f"No investigations could be matched confidently to Ward {ward}; preserving previous data")
    matched_address_rows = sum(len(app["addresses"]) for app in applications)
    quality = {
        "source_investigations": len(investigations),
        "source_address_rows": relevant_address_rows,
        "ward_investigations": len(applications),
        "matched_address_rows": matched_address_rows,
        "nonmatched_address_rows": relevant_address_rows - matched_address_rows - len(ambiguous_rows),
        "ambiguous_address_rows": len(ambiguous_rows),
        "investigations_with_deficiencies": sum(bool(app["deficiencies"]) for app in applications),
        "deficiency_rows": sum(len(app["deficiencies"]) for app in applications),
        "included_types": list(INCLUDED_TYPES),
        "note": "Addresses are matched to the City's One Address Repository. Nonmatched rows are predominantly outside the selected ward; ambiguous candidate addresses are excluded rather than guessed.",
    }
    raw = {
        "investigations": [investigations[investigation_id] for investigation_id in matched],
        "addresses": [address for app in applications for address in app["addresses"]],
        "deficiencies": [item for app in applications for item in app["deficiencies"]],
        "ambiguous_addresses": ambiguous_rows,
        "quality": quality,
    }
    return applications, quality, raw
