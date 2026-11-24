import { useState } from 'react'
import { ArrowUpRight, Download, FileJson, FileText } from 'lucide-react'
import type { Application, DashboardData } from '@/types'
import { formatDate, formatDateTime } from '@/lib/format'
import { ApplicationDetail } from './ApplicationDetail'

export function DigestView({ data }: { data: DashboardData }) {
  const [selectedDate, setSelectedDate] = useState(data.latest_digest.digest_date)
  const [selectedApp, setSelectedApp] = useState<Application | null>(null)
  const digest = data.recent_digests.find((item) => item.digest_date === selectedDate) ?? data.latest_digest

  return (
    <>
      <section className="page-heading">
        <div>
          <p className="eyebrow">Saved locally after every refresh</p>
          <h1>Daily digest</h1>
          <p>Newly visible applications and investigations, plus material record changes, compared with the previous successful snapshot.</p>
        </div>
        <div className="digest-downloads">
          <a className="primary-button" href={`digests/${digest.digest_date}.html`} download>
            <Download size={17} /> Download HTML
          </a>
          <a className="icon-button bordered" href={`digests/${digest.digest_date}.json`} download aria-label="Download digest JSON"><FileJson size={19} /></a>
        </div>
      </section>

      <div className="digest-layout">
        <div className="digest-main">
          <div className="digest-date-block">
            <div><span>Digest date</span><h2>{formatDate(digest.digest_date, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric', timeZone: 'UTC' })}</h2></div>
            <div className="digest-count"><strong>{digest.counts.new}</strong><span>newly visible</span></div>
            <div className="digest-count"><strong>{digest.counts.changed}</strong><span>changed records</span></div>
          </div>
          <p className="snapshot-note">Source captured {formatDateTime(digest.captured_at)}. “Newly visible” can differ from the application’s submission date.</p>

          {digest.baseline && (
            <section className="baseline-message">
              <h3>Baseline established</h3>
              <p>This is the first saved snapshot. Existing records have not been labelled as new; the next refresh will compare against this baseline.</p>
            </section>
          )}
          {digest.property_baseline && !digest.baseline && (
            <section className="baseline-message">
              <h3>Property Standards baseline established</h3>
              <p>Existing investigations in this first Property Standards snapshot have not been labelled as new. Future refreshes will compare against this baseline.</p>
            </section>
          )}

          <section className="digest-records">
            <div className="section-title-row"><h2>Newly visible records</h2><span>{digest.new_applications.length}</span></div>
            {digest.new_applications.length ? digest.new_applications.map((app) => (
              <article className="digest-record" key={app.id}>
                <div>
                  <p className={`category-text ${app.category}`}>{app.category_label} · {app.type_description}</p>
                  <h3>{app.application_number}</h3>
                  <p className="digest-address">{app.display_address}</p>
                  <p>{app.description}</p>
                  <p className="digest-record-meta">{app.category === 'property' ? 'Opened' : 'Submitted'} {formatDate(app.submitted_date)} · {app.status}</p>
                </div>
                <button className="row-open" onClick={() => setSelectedApp(app)} aria-label={`View ${app.application_number}`}><ArrowUpRight size={20} /></button>
              </article>
            )) : (
              <div className="empty-digest">
                <FileText size={24} aria-hidden="true" />
                <div><h3>{digest.baseline ? 'No comparison yet' : 'No newly visible records'}</h3><p>{digest.baseline ? 'New-record detection begins with the next snapshot.' : 'No record IDs appeared that were absent from the previous snapshot for their source.'}</p></div>
              </div>
            )}
          </section>

          {digest.changes.length > 0 && (
            <section className="digest-records change-section">
              <div className="section-title-row"><h2>Record changes</h2><span>{digest.changes.length}</span></div>
              {digest.changes.map((event) => (
                <details className="change-record" key={event.application.id}>
                  <summary><span>{event.application.application_number}</span><span>{event.application.display_address}</span></summary>
                  <dl>
                    {event.changes.map((change) => (
                      <div key={change.field}><dt>{change.label}</dt><dd><span>{change.before ?? 'Blank'}</span><strong>{change.after ?? 'Blank'}</strong></dd></div>
                    ))}
                  </dl>
                </details>
              ))}
            </section>
          )}

          {digest.submitted_today.length > 0 && (
            <section className="digest-records">
              <div className="section-title-row"><h2>Submitted or opened on this date</h2><span>{digest.submitted_today.length}</span></div>
              <p className="section-note">These records carry today’s application submission or investigation opening date, regardless of when they first became visible.</p>
              <ul className="submitted-list">{digest.submitted_today.map((app) => <li key={app.id}>{app.application_number} — {app.display_address}</li>)}</ul>
            </section>
          )}
        </div>

        <aside className="digest-history" aria-label="Recent digests">
          <h2>Saved history</h2>
          <p>Most recent 14 digest dates</p>
          <div>
            {data.recent_digests.map((item) => (
              <button key={item.captured_at} className={item.digest_date === selectedDate ? 'active' : ''} onClick={() => setSelectedDate(item.digest_date)}>
                <span>{formatDate(item.digest_date)}</span>
                <span>{item.baseline ? 'Baseline' : `${item.counts.new} new`}</span>
              </button>
            ))}
          </div>
        </aside>
      </div>
      {selectedApp && <ApplicationDetail application={selectedApp} onClose={() => setSelectedApp(null)} />}
    </>
  )
}
