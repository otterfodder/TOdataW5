"""Ward 5 Development Watch: official City ingestion, history, and digests.

Uses only the Python standard library. The City's public AIC ArcGIS layer
supplies Planning, C of A, and TLAB records. City open-data resources supply
Property Standards investigations and canonical ward addresses. No scraping,
geocoding service, credentials, or API keys are required.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import html
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from property_standards import (
    ADDRESS_POINTS_URL,
    INFORMATION_URL as PROPERTY_INFORMATION_URL,
    PACKAGE_URL as PROPERTY_PACKAGE_URL,
    fetch_property_data,
    load_property_data,
    normalize_property_standards,
)

ENDPOINT = (
    "https://services3.arcgis.com/b9WvedVPoizGfvfD/ArcGIS/rest/services/"
    "COTGEO_IBMS_AIC_POINT/FeatureServer/0/query"
)
LAYER_URL = ENDPOINT.removesuffix("/query")
SOURCE_PAGE = "https://www.toronto.ca/city-government/planning-development/application-information-centre/"
FIELDS = [
    "OBJECTID", "FOLDERRSN", "REFERENCEFILE", "APPLICATION_NUMBER",
    "FULL_ADDRESS", "FOLDERNAME", "FOLDERTYPE", "FOLDERTYPE_DESC",
    "APPLICATION_TYPE", "STATUS_DESC", "STATUS_GROUP", "RECORD_STATUS",
    "LATEST_MILESTONE", "LATEST_MILESTONE_DATE", "HEARING_DATE",
    "COMMUNITYMEETINGDATE", "SUBMIT_DATE", "COMPLETE_DATE", "INDATE",
    "LAST_MODIFIED_DATE", "FOLDERDESCRIPTION", "ASSIGNEDPLANNER",
    "ASSIGNEDPLANNER2", "PLANNEREMAIL", "PLANNERPHONE", "AIC_URL",
    "WARD_NUMBER", "WARD_NAME", "LONGITUDE", "LATITUDE", "AIC_ENCRYPTED_VALUE",
]
COMPARE_FIELDS = {
    "status": "Status",
    "status_group": "Open / closed group",
    "latest_milestone": "Latest milestone",
    "latest_milestone_date": "Milestone date",
    "hearing_date": "Hearing date",
    "community_meeting_date": "Community meeting date",
    "planner": "Assigned planner",
    "description": "Description / issue",
    "notice_or_order_date": "Notice / order date",
    "next_inspection": "Next inspection",
    "expiry_date": "Expiry date",
    "deficiency_summary": "Deficiencies",
}
CATEGORY_LABELS = {
    "planning": "Community Planning",
    "coa": "Committee of Adjustment",
    "tlab": "Toronto Local Appeal Body",
    "property": "Property Standards",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_date(epoch_ms: Any) -> str | None:
    if epoch_ms in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(float(epoch_ms) / 1000, timezone.utc).date().isoformat()
    except (ValueError, TypeError, OSError):
        return None


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(html.unescape(str(value)).split())
    return text or None


def category_key(value: Any) -> str:
    text = (clean_text(value) or "").lower()
    if "local appeal" in text or text == "tlab":
        return "tlab"
    if "c of a" in text or "adjustment" in text:
        return "coa"
    return "planning"


def fetch_features(ward: str = "05", retries: int = 3) -> list[dict[str, Any]]:
    """Fetch every address row for a ward, following ArcGIS pagination."""
    features: list[dict[str, Any]] = []
    offset = 0
    while True:
        params = {
            "where": f"WARD_NUMBER='{ward}'",
            "outFields": ",".join(FIELDS),
            "returnGeometry": "false",
            "orderByFields": "OBJECTID",
            "resultRecordCount": 1000,
            "resultOffset": offset,
            "f": "json",
        }
        request = urllib.request.Request(
            ENDPOINT + "?" + urllib.parse.urlencode(params),
            headers={"User-Agent": "Ward5DevelopmentWatch/1.0 (civic open-data reader)"},
        )
        payload = None
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(request, timeout=90) as response:
                    payload = json.load(response)
                break
            except Exception:
                if attempt == retries - 1:
                    raise
                time.sleep(2 ** attempt)
        if not payload or "error" in payload:
            raise RuntimeError(f"AIC returned an error: {payload.get('error', 'empty response')}")
        batch = payload.get("features", [])
        features.extend(batch)
        offset += len(batch)
        if not batch or not payload.get("exceededTransferLimit"):
            break
    if not features:
        raise RuntimeError(f"The AIC returned no Ward {ward} rows; refusing to replace good data.")
    return features


def normalize(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Consolidate address-level AIC features into application-level records."""
    grouped: dict[str, dict[str, Any]] = {}
    addresses: dict[str, dict[str, dict[str, Any]]] = {}
    for feature in features:
        a = feature.get("attributes", feature)
        folder_rsn = a.get("FOLDERRSN")
        if folder_rsn is None:
            continue
        app_id = str(folder_rsn)
        address = clean_text(a.get("FULL_ADDRESS")) or clean_text(a.get("FOLDERNAME"))
        if address:
            addresses.setdefault(app_id, {})[address] = {
                "address": address,
                "latitude": a.get("LATITUDE"),
                "longitude": a.get("LONGITUDE"),
            }
        if app_id in grouped:
            continue
        category = category_key(a.get("APPLICATION_TYPE"))
        address_list = list(addresses.get(app_id, {}).values())
        grouped[app_id] = {
            "id": app_id,
            "application_number": clean_text(a.get("REFERENCEFILE"))
                or clean_text(a.get("APPLICATION_NUMBER")) or f"AIC {app_id}",
            "reference_file": clean_text(a.get("REFERENCEFILE")),
            "folder_name": clean_text(a.get("FOLDERNAME")),
            "folder_type": clean_text(a.get("FOLDERTYPE")),
            "type_description": clean_text(a.get("FOLDERTYPE_DESC")),
            "category": category,
            "category_label": CATEGORY_LABELS[category],
            "status": clean_text(a.get("STATUS_DESC")) or "Not supplied",
            "status_group": clean_text(a.get("STATUS_GROUP")) or "Unknown",
            "record_status": clean_text(a.get("RECORD_STATUS")),
            "submitted_date": iso_date(a.get("SUBMIT_DATE") or a.get("INDATE")),
            "completed_date": iso_date(a.get("COMPLETE_DATE")),
            "latest_milestone": clean_text(a.get("LATEST_MILESTONE")),
            "latest_milestone_date": iso_date(a.get("LATEST_MILESTONE_DATE")),
            "hearing_date": iso_date(a.get("HEARING_DATE")),
            "community_meeting_date": iso_date(a.get("COMMUNITYMEETINGDATE")),
            "last_modified_date": iso_date(a.get("LAST_MODIFIED_DATE")),
            "description": clean_text(a.get("FOLDERDESCRIPTION")) or "No description supplied.",
            "planner": clean_text(a.get("ASSIGNEDPLANNER2") or a.get("ASSIGNEDPLANNER")),
            "planner_email": clean_text(a.get("PLANNEREMAIL")),
            "planner_phone": clean_text(a.get("PLANNERPHONE")),
            "aic_url": clean_text(a.get("AIC_URL")) or (
                "https://app.toronto.ca/AIC/index.do?folderRsn=" + str(a["AIC_ENCRYPTED_VALUE"])
                if a.get("AIC_ENCRYPTED_VALUE") else None
            ),
            "source_url": clean_text(a.get("AIC_URL")) or (
                "https://app.toronto.ca/AIC/index.do?folderRsn=" + str(a["AIC_ENCRYPTED_VALUE"])
                if a.get("AIC_ENCRYPTED_VALUE") else SOURCE_PAGE
            ),
            "ward_number": clean_text(a.get("WARD_NUMBER")),
            "ward_name": clean_text(a.get("WARD_NAME")),
            "addresses": address_list,
        }
    for app_id, app in grouped.items():
        app["addresses"] = sorted(
            addresses.get(app_id, {}).values(), key=lambda item: item["address"]
        )
        app["display_address"] = app["folder_name"] or (
            app["addresses"][0]["address"] if app["addresses"] else "Address not supplied"
        )
    return sorted(
        grouped.values(),
        key=lambda app: (app["submitted_date"] or "", app["application_number"]),
        reverse=True,
    )


def changes_between(previous: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    changes = []
    for field, label in COMPARE_FIELDS.items():
        if previous.get(field) != current.get(field):
            changes.append({
                "field": field,
                "label": label,
                "before": previous.get(field),
                "after": current.get(field),
            })
    return changes


def connect_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY,
            captured_at TEXT NOT NULL UNIQUE,
            address_rows INTEGER NOT NULL,
            application_count INTEGER NOT NULL,
            raw_file TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS snapshot_applications (
            snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
            application_id TEXT NOT NULL,
            data_json TEXT NOT NULL,
            PRIMARY KEY (snapshot_id, application_id)
        );
        CREATE TABLE IF NOT EXISTS applications (
            id TEXT PRIMARY KEY,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            data_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY,
            snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
            application_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            details_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    return db


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def production_state_path(project: Path, ward: str) -> Path:
    return project / "data" / "state" / f"ward-{ward}.json"


def write_production_state(
    project: Path,
    ward: str,
    captured_at: str,
    applications: list[dict[str, Any]],
    address_rows: int,
) -> Path:
    """Persist the small, normalized comparison state needed by a fresh runner."""
    records = [
        {key: value for key, value in app.items() if key != "is_new"}
        for app in applications
    ]
    state = {
        "schema_version": 1,
        "ward": ward,
        "captured_at": captured_at,
        "address_rows": address_rows,
        "applications": records,
    }
    path = production_state_path(project, ward)
    atomic_write(path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    return path


def restore_production_state(project: Path, ward: str) -> bool:
    """Rebuild the previous SQLite snapshot on an ephemeral runner.

    A malformed state file is a hard stop: silently treating it as a first run
    would mislabel every existing record as a baseline and lose change history.
    """
    path = production_state_path(project, ward)
    if not path.exists():
        return False
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("schema_version") != 1 or state.get("ward") != ward:
            raise ValueError("unsupported state schema or ward")
        captured_at = datetime.fromisoformat(state["captured_at"]).isoformat()
        applications = state["applications"]
        if not isinstance(applications, list) or not applications:
            raise ValueError("state contains no applications")
        ids = [str(app["id"]) for app in applications]
        if len(ids) != len(set(ids)):
            raise ValueError("state contains duplicate application IDs")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Saved production state {path} could not be restored; "
            "refusing to start a new baseline."
        ) from exc

    db = connect_db(project / "data" / f"ward-{ward}-applications.db")
    try:
        if db.execute("SELECT 1 FROM snapshots LIMIT 1").fetchone():
            return False
        with db:
            cursor = db.execute(
                "INSERT INTO snapshots(captured_at,address_rows,application_count,raw_file) VALUES(?,?,?,?)",
                (captured_at, int(state.get("address_rows", 0)), len(applications), str(path.relative_to(project))),
            )
            snapshot_id = cursor.lastrowid
            for app in applications:
                data_json = json.dumps(app, ensure_ascii=False)
                db.execute(
                    "INSERT INTO snapshot_applications VALUES(?,?,?)",
                    (snapshot_id, str(app["id"]), data_json),
                )
                db.execute(
                    "INSERT INTO applications(id,first_seen,last_seen,data_json) VALUES(?,?,?,?)",
                    (
                        str(app["id"]),
                        app.get("first_seen") or captured_at[:10],
                        app.get("last_seen") or captured_at[:10],
                        data_json,
                    ),
                )
            db.execute("INSERT INTO metadata(key,value) VALUES('latest_snapshot',?)", (str(snapshot_id),))
        return True
    finally:
        db.close()


def csv_safe(value: Any) -> Any:
    """Prevent spreadsheet programs from evaluating text as a formula."""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def application_csv_rows(applications: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for app in applications:
        rows.append({
            "application_id": app["id"],
            "application_number": app["application_number"],
            "category": app["category_label"],
            "application_type": app["type_description"],
            "status_group": app["status_group"],
            "status": app["status"],
            "submitted_date": app["submitted_date"],
            "addresses": "; ".join(item["address"] for item in app["addresses"]),
            "description": app["description"],
            "latest_milestone": app["latest_milestone"],
            "latest_milestone_date": app["latest_milestone_date"],
            "hearing_date": app["hearing_date"],
            "community_meeting_date": app["community_meeting_date"],
            "planner": app["planner"],
            "planner_email": app["planner_email"],
            "planner_phone": app["planner_phone"],
            "investigation_id": app.get("investigation_id"),
            "notice_or_order_date": app.get("notice_or_order_date"),
            "next_inspection": app.get("next_inspection"),
            "expiry_date": app.get("expiry_date"),
            "issue": app.get("issue"),
            "deficiencies": app.get("deficiency_summary"),
            "official_source_url": app.get("source_url") or app["aic_url"],
        })
    return rows


def write_csv(path: Path, applications: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    rows = [
        {key: csv_safe(value) for key, value in row.items()}
        for row in application_csv_rows(applications)
    ]
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [
            "application_id", "application_number", "category", "application_type",
            "status_group", "status", "submitted_date", "addresses", "description",
            "latest_milestone", "latest_milestone_date", "hearing_date",
            "community_meeting_date", "planner", "planner_email", "planner_phone",
            "investigation_id", "notice_or_order_date", "next_inspection", "expiry_date",
            "issue", "deficiencies", "official_source_url",
        ])
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def digest_html(digest: dict[str, Any]) -> str:
    date = html.escape(digest["digest_date"])
    cards = []
    if digest["baseline"]:
        cards.append(
            '<section class="empty"><h2>Baseline established</h2>'
            '<p>This first snapshot is the comparison point for new-application detection. '
            'No existing records have been labelled as newly submitted.</p></section>'
        )
    if digest.get("property_baseline") and not digest["baseline"]:
        cards.append(
            '<section class="empty"><h2>Property Standards baseline established</h2>'
            '<p>The existing investigations in this first Property Standards snapshot are the comparison '
            'point for future changes. They have not been labelled as newly submitted.</p></section>'
        )
    elif not digest["new_applications"] and not digest["baseline"]:
        cards.append(
            '<section class="empty"><h2>No newly visible applications</h2>'
            '<p>No application IDs appeared that were absent from the previous snapshot.</p></section>'
        )
    for app in digest["new_applications"]:
        addresses = html.escape("; ".join(a["address"] for a in app["addresses"]))
        source_url = app.get("source_url") or app.get("aic_url")
        source_label = "Open City investigation search" if app["category"] == "property" else "Open in the City AIC"
        link = (f'<a href="{html.escape(source_url, quote=True)}">{source_label}</a>'
                if source_url else "")
        cards.append(f"""
        <article class="application">
          <p class="category">{html.escape(app['category_label'])} · {html.escape(app['type_description'] or '')}</p>
          <h2>{html.escape(app['application_number'])}</h2>
          <p class="address">{html.escape(app['display_address'])}</p>
          <dl><dt>Submitted</dt><dd>{html.escape(app['submitted_date'] or 'Not supplied')}</dd>
          <dt>Status</dt><dd>{html.escape(app['status'])}</dd>
          <dt>All addresses</dt><dd>{addresses}</dd></dl>
          <p>{html.escape(app['description'])}</p>{link}
        </article>""")
    changes = []
    for event in digest["changes"]:
        app = event["application"]
        detail = "; ".join(
            f"{c['label']}: {c['before'] or 'blank'} → {c['after'] or 'blank'}"
            for c in event["changes"]
        )
        changes.append(f"<li><strong>{html.escape(app['application_number'])}</strong> — {html.escape(detail)}</li>")
    change_section = ""
    if changes:
        change_section = '<section><h2>Other record changes</h2><ul>' + "".join(changes) + "</ul></section>"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Ward 5 Development Watch — {date}</title><style>
    body{{max-width:800px;margin:40px auto;padding:0 24px;background:#edf5f4;color:#102528;font:16px/1.6 Arial,sans-serif}}
    header{{border-bottom:2px solid #759da3;padding-bottom:20px}}h1{{font-size:32px;line-height:1.2}}h2{{font-size:20px}}
    .meta,.category{{color:#345c62}}.application,.empty,section{{border-top:1px solid #9dbbc0;padding:24px 0}}
    .address{{font-size:20px;font-weight:600}}dl{{display:grid;grid-template-columns:140px 1fr}}dt{{font-weight:600}}dd{{margin:0}}
    a{{color:#0e5b63}}li{{margin:12px 0}}</style></head><body>
    <header><h1>Ward 5 Development Watch</h1><p>Daily application digest · {date}</p>
    <p class="meta">{len(digest['new_applications'])} newly visible · {len(digest['changes'])} changed records ·
    Source captured {html.escape(digest['captured_at'])}</p></header>
    {''.join(cards)}{change_section}
    <footer><p>Sources: City of Toronto Application Information Centre public map layer; Municipal Licensing and Standards Investigation Activity; and the One Address Repository. Newly visible means absent from the previous successful snapshot for that source; it may differ from the submission or investigation date.</p></footer>
    </body></html>"""


def load_recent_digests(directory: Path, limit: int = 14) -> list[dict[str, Any]]:
    digests = []
    for path in sorted(directory.glob("*.json"), reverse=True)[:limit]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            digests.append(data)
        except (OSError, json.JSONDecodeError):
            continue
    return digests


def refresh(
    project: Path,
    ward: str,
    input_path: Path | None = None,
    property_input: Path | None = None,
    include_property: bool = True,
) -> dict[str, Any]:
    restore_production_state(project, ward)
    captured = utc_now()
    captured_at = captured.isoformat(timespec="microseconds")
    digest_date = captured.astimezone(ZoneInfo("America/Toronto")).date().isoformat()
    if input_path:
        features = json.loads(input_path.read_text(encoding="utf-8")).get("features", [])
    else:
        features = fetch_features(ward)
    aic_applications = normalize(features)
    if not aic_applications:
        raise RuntimeError("No valid AIC application IDs were found; existing outputs were preserved.")

    property_quality: dict[str, Any] = {
        "source_investigations": 0,
        "source_address_rows": 0,
        "ward_investigations": 0,
        "matched_address_rows": 0,
        "nonmatched_address_rows": 0,
        "ambiguous_address_rows": 0,
        "investigations_with_deficiencies": 0,
        "deficiency_rows": 0,
        "included_types": [],
        "note": "Property Standards ingestion was skipped for this run.",
    }
    property_raw: dict[str, Any] | None = None
    property_applications: list[dict[str, Any]] = []
    if include_property:
        property_data = load_property_data(property_input) if property_input else fetch_property_data(ward)
        property_applications, property_quality, property_raw = normalize_property_standards(property_data, ward)
    applications = aic_applications + property_applications
    for app in applications:
        app["first_seen"] = digest_date
        app["last_seen"] = digest_date

    db_path = project / "data" / f"ward-{ward}-applications.db"
    db = connect_db(db_path)
    try:
        previous_row = db.execute("SELECT * FROM snapshots ORDER BY id DESC LIMIT 1").fetchone()
        previous = {}
        if previous_row:
            previous = {
                row["application_id"]: json.loads(row["data_json"])
                for row in db.execute(
                    "SELECT * FROM snapshot_applications WHERE snapshot_id = ?", (previous_row["id"],)
                )
            }
        had_property = any(app.get("category") == "property" for app in previous.values())
        property_baseline = include_property and not had_property
        new_apps = []
        if previous_row:
            new_apps = [
                app for app in applications
                if app["id"] not in previous and not (app["category"] == "property" and property_baseline)
            ]
        new_ids = {app["id"] for app in new_apps}
        changed = []
        if previous_row:
            for app in applications:
                if app["id"] in previous:
                    changes = changes_between(previous[app["id"]], app)
                    if changes:
                        changed.append({"application": app, "changes": changes})
        submitted_today = [app for app in applications if app["submitted_date"] == digest_date]

        raw_relative = Path("data") / "snapshots" / f"{captured.strftime('%Y-%m-%dT%H%M%S%fZ')}.json"
        raw_path = project / raw_relative
        atomic_write(raw_path, json.dumps({"features": features}, ensure_ascii=False, separators=(",", ":")))
        if property_raw is not None:
            property_raw_path = raw_path.with_name(raw_path.stem + "-property-standards.json.gz")
            temporary = property_raw_path.with_suffix(property_raw_path.suffix + ".tmp")
            property_raw_path.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(temporary, "wt", encoding="utf-8") as handle:
                json.dump(property_raw, handle, ensure_ascii=False, separators=(",", ":"))
            os.replace(temporary, property_raw_path)
        with db:
            cursor = db.execute(
                "INSERT INTO snapshots(captured_at,address_rows,application_count,raw_file) VALUES(?,?,?,?)",
                (captured_at, len(features), len(applications), str(raw_relative)),
            )
            snapshot_id = cursor.lastrowid
            for app in applications:
                existing = db.execute("SELECT first_seen FROM applications WHERE id=?", (app["id"],)).fetchone()
                app["first_seen"] = existing["first_seen"] if existing else digest_date
                db.execute(
                    "INSERT INTO snapshot_applications VALUES(?,?,?)",
                    (snapshot_id, app["id"], json.dumps(app, ensure_ascii=False)),
                )
                db.execute(
                    "INSERT INTO applications(id,first_seen,last_seen,data_json) VALUES(?,?,?,?) "
                    "ON CONFLICT(id) DO UPDATE SET last_seen=excluded.last_seen,data_json=excluded.data_json",
                    (app["id"], app["first_seen"], digest_date, json.dumps(app, ensure_ascii=False)),
                )
                if app["id"] in new_ids:
                    db.execute(
                        "INSERT INTO events(snapshot_id,application_id,event_type,details_json) VALUES(?,?,?,?)",
                        (snapshot_id, app["id"], "new", "{}"),
                    )
            for event in changed:
                db.execute(
                    "INSERT INTO events(snapshot_id,application_id,event_type,details_json) VALUES(?,?,?,?)",
                    (snapshot_id, event["application"]["id"], "changed", json.dumps(event["changes"], ensure_ascii=False)),
                )
            db.execute(
                "INSERT INTO metadata(key,value) VALUES('latest_snapshot',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(snapshot_id),),
            )
    finally:
        db.close()

    open_apps = [app for app in applications if app["status_group"].lower() == "open"]
    category_counts = Counter(app["category"] for app in open_apps)
    digest = {
        "digest_date": digest_date,
        "captured_at": captured_at,
        "previous_captured_at": previous_row["captured_at"] if previous_row else None,
        "baseline": not bool(previous_row),
        "property_baseline": property_baseline,
        "new_applications": new_apps,
        "changes": changed,
        "submitted_today": submitted_today,
        "counts": {
            "address_rows": len(features),
            "applications": len(applications),
            "open_applications": len(open_apps),
            "property_investigations": len(property_applications),
            "new": len(new_apps),
            "changed": len(changed),
        },
    }
    digest_dir = project / "digests"
    atomic_write(digest_dir / f"{digest_date}.json", json.dumps(digest, ensure_ascii=False, indent=2))
    atomic_write(digest_dir / f"{digest_date}.html", digest_html(digest))
    write_csv(digest_dir / f"{digest_date}-new.csv", new_apps)
    export_path = project / "exports" / f"ward-{ward}-applications-{digest_date}.csv"
    write_csv(export_path, applications)

    recent_digests = load_recent_digests(digest_dir)
    public_data = {
        "generated_at": captured_at,
        "ward": {"number": ward, "name": "York South-Weston" if ward == "05" else f"Ward {ward}"},
        "source": {
            "name": "City of Toronto Application Information Centre",
            "layer_url": LAYER_URL,
            "information_url": SOURCE_PAGE,
            "address_rows": len(features),
            "applications": len(aic_applications),
            "coverage": ["Community Planning", "Committee of Adjustment", "Toronto Local Appeal Body"],
            "note": "The AIC lists active cases and some recently closed cases. This dashboard is a snapshot, not the City’s legal record.",
        },
        "property_source": {
            "name": "City of Toronto Municipal Licensing and Standards Investigation Activity",
            "package_url": PROPERTY_PACKAGE_URL,
            "information_url": PROPERTY_INFORMATION_URL,
            "address_points_url": ADDRESS_POINTS_URL,
            **property_quality,
        },
        "stats": {
            "applications": len(applications),
            "aic_applications": len(aic_applications),
            "property_records": len(property_applications),
            "open": len(open_apps),
            "closed": len(applications) - len(open_apps),
            "planning": category_counts["planning"],
            "coa": category_counts["coa"],
            "tlab": category_counts["tlab"],
            "property": category_counts["property"],
            "new": len(new_apps),
            "changed": len(changed),
        },
        "applications": applications,
        "latest_digest": digest,
        "recent_digests": recent_digests,
        "downloads": {
            "all_csv": f"exports/ward-{ward}-applications.csv",
            "latest_digest_html": f"digests/{digest_date}.html",
            "latest_digest_json": f"digests/{digest_date}.json",
        },
    }
    (project / "public" / "exports").mkdir(parents=True, exist_ok=True)
    (project / "public" / "digests").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(export_path, project / "public" / "exports" / f"ward-{ward}-applications.csv")
    for item in recent_digests:
        for extension in ("html", "json"):
            source = digest_dir / f"{item['digest_date']}.{extension}"
            if source.exists():
                shutil.copyfile(source, project / "public" / "digests" / source.name)
    shutil.copyfile(digest_dir / f"{digest_date}-new.csv", project / "public" / "digests" / f"{digest_date}-new.csv")
    for app in applications:
        app["is_new"] = app["id"] in new_ids
    serialized = json.dumps(public_data, ensure_ascii=False, separators=(",", ":"))
    atomic_write(project / "public" / "data" / "latest.json", json.dumps(public_data, ensure_ascii=False, indent=2))
    atomic_write(project / "public" / "data" / "latest.js", "window.__WARD5_DATA__=" + serialized + ";")
    write_production_state(project, ward, captured_at, applications, len(features))
    return public_data


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh the Ward City-record database and daily digest.")
    parser.add_argument("--ward", default="05", help="Two-digit Toronto ward number (default: 05)")
    parser.add_argument("--input", type=Path, help="Use a saved ArcGIS response instead of the live AIC feed")
    parser.add_argument("--property-input", type=Path, help="Use a saved four-file Property Standards source directory")
    parser.add_argument("--build", action="store_true", help="Rebuild the standalone browser dashboard afterwards")
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    try:
        data = refresh(project, args.ward.zfill(2), args.input, args.property_input)
        if args.build:
            subprocess.run(["npm", "run", "build"], cwd=project, check=True)
    except Exception as exc:
        print(f"Refresh failed: {exc}", file=sys.stderr)
        print("Previous database, dashboard data, and digests were left available.", file=sys.stderr)
        return 1
    stats = data["stats"]
    print(
        f"Ward {data['ward']['number']}: {stats['applications']} records "
        f"({stats['open']} open; {stats['property_records']} Property Standards investigations), "
        f"{stats['new']} new, {stats['changed']} changed."
    )
    print(f"Digest: {project / 'digests' / (data['latest_digest']['digest_date'] + '.html')}")
    print(f"Database: {project / 'data' / ('ward-' + data['ward']['number'] + '-applications.db')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
