# Ward 5 Development Watch

A local database, browser dashboard, CSV exporter, and daily saved digest for current City of Toronto records in **Ward 5, York South–Weston**.

It covers four categories:

- Community Planning
- Committee of Adjustment (C of A)
- Toronto Local Appeal Body (TLAB)
- Property Standards investigations

The dashboard defaults to open records. Recently closed records supplied by the City remain available through the status filter.

## Official sources

### Application Information Centre

The City's public `COTGEO_IBMS_AIC_POINT` ArcGIS layer supplies all three AIC categories. Address-level features are consolidated into applications using the City's `FOLDERRSN` folder identifier.

### Property Standards

The Municipal Licensing and Standards Investigation Activity open-data package supplies investigations, addresses, and deficiencies. The register includes these investigation types:

- `Property Standards`
- `Order Issued Property Standards`
- `Notice Issued Prop Standards`

Investigation addresses are matched to the City's One Address Repository, whose canonical address points include the current municipal ward. Exact component matches are preferred. A house-number/street fallback is accepted only when it resolves to one canonical address. Ambiguous candidates are excluded and reported rather than guessed.

The Property Standards dataset describes active matters and matters closed within the last two years. Complaints appear only after officer action; invalid and cancelled complaints are excluded. The register is a snapshot, not the City's legal enforcement record.

## What each refresh does

1. Retrieves every Ward 5 address row from the AIC layer.
2. Downloads the investigation, address, deficiency, and Ward 5 address-point resources.
3. Consolidates AIC applications and joins Property Standards investigations to their addresses and deficiencies.
4. Stores timestamped snapshots and normalized history in SQLite.
5. Compares record IDs and material fields with the previous successful snapshot.
6. Saves a standalone HTML digest, machine-readable JSON, a new-record CSV, and a complete register CSV.
7. Updates the browser dashboard, optionally rebuilding the standalone `dist/` version.

The first refresh establishes a baseline and deliberately reports zero newly visible records. Adding Property Standards to an existing AIC database creates a **separate Property Standards baseline**, so existing investigations are not falsely labelled as new. Later refreshes report IDs absent from the previous snapshot for that source. This is **newly visible**, which is not necessarily the same as submitted or opened that day. Records carrying the current submission/investigation date are listed separately when present.

If either source fails or returns no valid records, the run exits nonzero without replacing the last good dashboard or digest.

## Requirements

- Python 3.10 or newer; ingestion uses only the standard library.
- Node.js 20 or newer and npm for building the dashboard.
- An internet connection for live refreshes.

No City account, API key, geocoding service, scraping browser, or Python package installation is required.

## Quick start

From this project folder:

```bash
npm install
python3 scripts/wardwatch.py --ward 05 --build
```

Open `dist/index.html` directly in a browser. For development with automatic browser reload:

```bash
npm run dev
```

To refresh without rebuilding the dashboard:

```bash
python3 scripts/wardwatch.py --ward 05
```

For a reproducible offline refresh, `--input` accepts a saved AIC ArcGIS response and `--property-input` accepts a directory containing `investigations`, `addresses`, `deficiencies`, and `address_points` JSON or CSV files:

```bash
python3 scripts/wardwatch.py --ward 05 --input aic.json --property-input saved-property-sources --build
```

## Production hosting: GitHub Pages + GitHub Actions

This is the recommended low-maintenance production setup. It needs only a GitHub account and does not require a server, City credential, custom API key, or always-on computer. GitHub Pages serves the static dashboard; GitHub Actions refreshes it daily at **7:23 a.m. Toronto time**.

Kimi Publish remains appropriate for sharing the visual prototype and its bundled data snapshot. It does **not** run the Python ingestion on a schedule. Firebase Hosting is a viable Google alternative, but it adds a second account and deployment credentials without simplifying this dashboard’s daily update.

### One-time go-live steps

1. Create a **public** GitHub repository and push this project to its `main` branch. A public repository allows GitHub Pages on the free plan; all bundled information already comes from public City sources.
2. In **Settings → Actions → General → Workflow permissions**, select **Read and write permissions**. The updater needs this to save the normalized state and dated digests back to the repository.
3. In **Settings → Pages**, choose **GitHub Actions** as the deployment source if it is not selected automatically.
4. Open **Actions**, enable workflows if GitHub prompts you, select **Update and publish Ward 5 Watch**, and choose **Run workflow**. This same control provides a manual refresh later.
5. Wait for both the update and deployment stages to succeed. The public address appears under **Settings → Pages** and in the deployment output. It normally follows `https://GITHUB-NAME.github.io/REPOSITORY/`.
6. Enable GitHub Actions failure notifications in the account’s notification settings. A failed run leaves the previous good website online; the dashboard also warns visitors when its data is more than 36 hours old.
7. Run the workflow a second time as the go-live rehearsal. The existing records must remain in place, and the second run must not label the whole register as new.

A custom domain can later be added under **Settings → Pages**. No Firebase or Google Cloud setup is needed for the recommended configuration.

### What each production run preserves

- `data/state/ward-05.json` is the normalized comparison state. A fresh scheduled runner restores it into SQLite before calculating new and changed records.
- `digests/` retains dated HTML, JSON, and newly-visible-record CSV history.
- `public/` contains the current dashboard data and downloadable files that are packaged into the release.
- Raw City snapshots, dated full-register exports, Python caches, and SQLite databases are local/disposable artifacts and are not committed daily.

The workflow runs regression tests and static checks before ingestion, validates the complete release afterward, prevents overlapping runs, and deploys in a separate stage. Any failure stops publication and retains the last good deployment.

## Local daily automation

For a locally managed copy, run once daily after the City's refresh, for example at 8:15 a.m. Toronto time.

### macOS or Linux

```cron
15 8 * * * cd /path/to/project && /usr/bin/python3 scripts/wardwatch.py --ward 05 --build >> refresh.log 2>&1
```

Or run:

```bash
bash scripts/run_daily.sh
```

### Windows

Create a daily Task Scheduler task with this program/arguments, adjusted for the Python installation:

```text
python scripts\wardwatch.py --ward 05 --build
```

Set **Start in** to the project folder. `scripts\run_daily.bat` provides the same command as a reusable task action.

## Files

| Path | Purpose |
| --- | --- |
| `data/state/ward-05.json` | Persistent normalized comparison state for cloud and local runs |
| `data/ward-05-applications.db` | Rebuildable local SQLite records, snapshots, and change events |
| `data/snapshots/` | Local raw timestamped AIC responses and compressed Property Standards snapshots |
| `digests/YYYY-MM-DD.html` | Standalone daily digest |
| `digests/YYYY-MM-DD.json` | Digest records and change details |
| `digests/YYYY-MM-DD-new.csv` | Newly visible records |
| `exports/` | Dated complete-register CSV files |
| `public/data/latest.js` | Bundled dashboard snapshot |
| `dist/index.html` | Standalone built dashboard |
| `validation/live-source-validation.json` | Latest independent live-source comparison report |

Repeating a refresh on the same date updates that date's digest files while retaining each snapshot in SQLite. The dashboard keeps the most recent 14 digest dates available in its history view.

## Search, details, and exports

The register supports address/file/proposal/deficiency/planner search, category, status, and type filters, sorting, and pagination. **Export** downloads the currently filtered records as CSV.

AIC rows open a detail drawer with addresses, dates, proposal, planner contact information, and the official AIC link. Property Standards rows show the issue, notice/order date, next inspection, expiry date, matched addresses, and deficiency details. The City investigation feed does not provide permanent record-level URLs, so its button opens the official investigation search page.

CSV output protects spreadsheet users by prefixing values that could otherwise be interpreted as formulas.

## Tests and live validation

```bash
python3 -m unittest discover -s scripts -p 'test_*.py' -v
npm run lint
npm run build
python3 scripts/validate_release.py
python3 scripts/validate_live.py
```

The regression tests cover AIC consolidation and categories, source entity decoding, Property Standards address/deficiency joins, ambiguous-address refusal, separate baselines, new-record detection, material changes, output generation, cloud-state restoration on a fresh runner, and refusal to reset history from damaged state.

`validate_release.py` checks the complete static release without additional network requests: record IDs, category and count consistency, production-state alignment, browser/JSON data equality, CSV row counts, digest downloads, and built-file freshness. The production workflow runs it before deployment.

`validate_live.py` performs fresh downloads from the official sources and compares every current dashboard record by ID, addresses, status, category/type, dates, contacts, and deficiencies. It writes `validation/live-source-validation.json` and exits nonzero on any mismatch. The interactive AIC website may block automated browsers; validation uses the live official ArcGIS layer behind the AIC.

## Changing wards

The ingestion command accepts another two-digit Toronto ward number:

```bash
python3 scripts/wardwatch.py --ward 01 --build
```

The dashboard branding and explanatory text are tailored to Ward 5, so additional wards currently require corresponding text changes in the frontend.

## Licence and limitations

Sources:

- [City of Toronto Application Information Centre](https://www.toronto.ca/city-government/planning-development/application-information-centre/)
- [Municipal Licensing and Standards Investigation Activity](https://open.toronto.ca/dataset/municipal-licensing-and-standards-investigation-activity/)
- [Address Points — Toronto One Address Repository](https://open.toronto.ca/dataset/address-points-municipal-toronto-one-address-repository/)

The AIC provides active cases and some closed cases, not a complete historical archive. Confirm documents, status, dates, and enforcement details with the City before relying on them.

Contains information licensed under the [Open Government Licence – Toronto](https://www.toronto.ca/home/copyright-information/).
