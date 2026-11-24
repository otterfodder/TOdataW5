import { useState } from 'react'
import { Check, Copy, Database, Download, ExternalLink, FileClock, ShieldCheck } from 'lucide-react'
import type { DashboardData } from '@/types'
import { formatDateTime } from '@/lib/format'

function CopyCommand({ command }: { command: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(command)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = command
        textarea.style.position = 'fixed'
        textarea.style.opacity = '0'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        textarea.remove()
      }
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      setCopied(false)
    }
  }
  return (
    <div className="command-row">
      <code>{command}</code>
      <button className="icon-button" onClick={copy} aria-label="Copy refresh command">{copied ? <Check size={18} /> : <Copy size={18} />}</button>
      <span className="sr-only" aria-live="polite">{copied ? 'Copied' : ''}</span>
    </div>
  )
}

export function DataView({ data }: { data: DashboardData }) {
  const property = data.property_source
  return (
    <>
      <section className="page-heading">
        <div>
          <p className="eyebrow">Sources, files, and scheduling</p>
          <h1>Data & automation</h1>
          <p>Two official City data paths supply all four record categories. Every successful run preserves the previous state for comparison.</p>
        </div>
        <a className="primary-button" href={data.downloads.all_csv} download><Download size={17} /> Full register CSV</a>
      </section>

      <section className="data-section">
        <div className="data-section-heading"><Database size={21} /><div><h2>Application Information Centre</h2><p>Public ArcGIS layer · Planning, Committee of Adjustment, and TLAB</p></div></div>
        <div className="source-grid">
          <div><span>Community Planning</span><strong>{data.stats.planning}</strong><small>open applications</small></div>
          <div><span>Committee of Adjustment</span><strong>{data.stats.coa}</strong><small>open applications</small></div>
          <div><span>Toronto Local Appeal Body</span><strong>{data.stats.tlab}</strong><small>open applications</small></div>
        </div>
        <dl className="source-facts">
          <div><dt>Last successful capture</dt><dd>{formatDateTime(data.generated_at)}</dd></div>
          <div><dt>Source rows</dt><dd>{data.source.address_rows} address-level features</dd></div>
          <div><dt>Consolidated AIC register</dt><dd>{data.source.applications ?? data.stats.aic_applications ?? 0} applications, with multiple addresses grouped by City folder ID</dd></div>
        </dl>
        <a className="source-link" href={data.source.layer_url} target="_blank" rel="noreferrer">Inspect the City map layer <ExternalLink size={15} /></a>
        <p className="source-disclaimer">{data.source.note}</p>
      </section>

      <section className="data-section">
        <div className="data-section-heading"><Database size={21} /><div><h2>Property Standards investigations</h2><p>Investigation Activity open data · matched to Ward 5 through the City’s One Address Repository</p></div></div>
        <div className="source-grid property-source-grid">
          <div><span>Property Standards</span><strong>{data.stats.property}</strong><small>open investigations</small></div>
          <div><span>Ward 5 register</span><strong>{property.ward_investigations}</strong><small>open + recently closed</small></div>
          <div><span>Deficiency details</span><strong>{property.deficiency_rows}</strong><small>rows across {property.investigations_with_deficiencies} investigations</small></div>
          <div><span>Excluded as ambiguous</span><strong>{property.ambiguous_address_rows}</strong><small>address rows not guessed</small></div>
        </div>
        <dl className="source-facts">
          <div><dt>Included investigation types</dt><dd>{property.included_types.join(' · ')}</dd></div>
          <div><dt>Address join</dt><dd>{property.matched_address_rows} Ward 5 investigation addresses matched to canonical City address points</dd></div>
          <div><dt>Coverage note</dt><dd>{property.note}</dd></div>
        </dl>
        <div className="source-links">
          <a className="source-link" href={property.package_url} target="_blank" rel="noreferrer">Investigation open data <ExternalLink size={15} /></a>
          <a className="source-link" href={property.address_points_url} target="_blank" rel="noreferrer">Address repository <ExternalLink size={15} /></a>
          <a className="source-link" href={property.information_url} target="_blank" rel="noreferrer">City investigation search <ExternalLink size={15} /></a>
        </div>
        <p className="source-disclaimer">The dataset includes active matters and matters closed within the last two years. Complaints appear only after officer action; invalid or cancelled complaints are excluded. Confirm enforcement details with the City.</p>
      </section>

      <section className="data-section">
        <div className="data-section-heading"><FileClock size={21} /><div><h2>Refresh and daily files</h2><p>The exported project can refresh from the City with Python 3 and Node.js installed.</p></div></div>
        <CopyCommand command="python3 scripts/wardwatch.py --ward 05 --build" />
        <div className="file-explainer">
          <div><code>data/ward-05-applications.db</code><p>SQLite database with snapshots, record history, and change events.</p></div>
          <div><code>digests/YYYY-MM-DD.html</code><p>Standalone daily digest that opens in any browser.</p></div>
          <div><code>exports/</code><p>Dated CSV exports of the complete current register.</p></div>
          <div><code>dist/index.html</code><p>Updated standalone dashboard after the build step.</p></div>
        </div>
        <p className="automation-note"><ShieldCheck size={18} />If either City source fails or returns no valid records, the run stops without replacing the last good dashboard or digest. Each source has its own first-run baseline.</p>
      </section>

      <section className="data-section schedule-section">
        <div><h2>Hosting and daily updates</h2><p>The production configuration uses GitHub Actions to refresh the register and GitHub Pages to publish it. No server, City credential, or always-on computer is required.</p></div>
        <p>Once the repository is connected and GitHub Pages is set to <strong>GitHub Actions</strong>, the included workflow runs daily at 7:23 a.m. Toronto time and can also be started manually from the repository’s Actions tab. It restores the previous normalized snapshot, tests the update, preserves dated digests, and publishes only a valid release.</p>
        <p>A failed run leaves the last good website in place. GitHub can email the repository owner when a workflow fails, and the dashboard displays a warning when its snapshot is more than 36 hours old.</p>
        <details>
          <summary>What production stores</summary>
          <p>The repository keeps <code>data/state/ward-05.json</code> for comparison and dated digest files for history. Raw City downloads, dated CSV exports, and the SQLite database are disposable local artifacts and are not committed every day.</p>
        </details>
        <details>
          <summary>macOS or Linux cron example</summary>
          <p>For a locally managed copy, open your crontab, replace the project path, and use the Python path shown by <code>which python3</code>. The example runs at 8:15 a.m. Toronto time.</p>
          <pre>15 8 * * * cd /path/to/project &amp;&amp; /usr/bin/python3 scripts/wardwatch.py --ward 05 --build &gt;&gt; refresh.log 2&gt;&amp;1</pre>
        </details>
        <details>
          <summary>Windows Task Scheduler</summary>
          <p>Create a daily task whose action runs <code>python scripts\wardwatch.py --ward 05 --build</code>, with the exported project folder set as “Start in.” Use the full path to your Python executable if it is not on PATH.</p>
        </details>
        <p className="preview-note">Kimi Publish remains useful for sharing this prototype’s bundled snapshot. The scheduled production workflow becomes active only after the project is pushed to GitHub and the workflow is enabled.</p>
      </section>
    </>
  )
}
