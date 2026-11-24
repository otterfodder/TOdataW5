import { useEffect, useRef } from 'react'
import { CalendarDays, ClipboardList, ExternalLink, Mail, MapPin, Phone, X } from 'lucide-react'
import type { Application } from '@/types'
import { formatDate } from '@/lib/format'

export function ApplicationDetail({ application, onClose }: { application: Application; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    closeRef.current?.focus()
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    document.body.classList.add('drawer-open')
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.classList.remove('drawer-open')
      previous?.focus()
    }
  }, [onClose])

  const isProperty = application.category === 'property'
  const details = isProperty ? [
    ['Status', application.status],
    ['Open / closed', application.status_group],
    ['Investigation type', application.type_description],
    ['Investigation ID', application.investigation_id],
    ['Opened', formatDate(application.submitted_date)],
    ['Notice / order date', formatDate(application.notice_or_order_date)],
    ['Next inspection', formatDate(application.next_inspection)],
    ['Expiry date', formatDate(application.expiry_date)],
    ['First seen by this tool', formatDate(application.first_seen)],
  ] : [
    ['Status', application.status],
    ['Open / closed', application.status_group],
    ['Application type', application.type_description],
    ['Submitted', formatDate(application.submitted_date)],
    ['Latest milestone', application.latest_milestone],
    ['Milestone date', formatDate(application.latest_milestone_date)],
    ['Hearing', formatDate(application.hearing_date)],
    ['Community meeting', formatDate(application.community_meeting_date)],
    ['First seen by this tool', formatDate(application.first_seen)],
  ]
  const sourceUrl = application.source_url || application.aic_url

  return (
    <div className="drawer-layer">
      <button className="drawer-backdrop" onClick={onClose} aria-label="Close record details" />
      <section className="detail-drawer" role="dialog" aria-modal="true" aria-labelledby="application-title">
        <div className="drawer-topline">
          <span>{application.category_label}</span>
          <button ref={closeRef} className="icon-button" onClick={onClose} aria-label="Close record details"><X size={22} /></button>
        </div>
        <div className="drawer-heading">
          <p className="record-kicker">{application.folder_type || 'Application'} record</p>
          <h2 id="application-title">{application.application_number}</h2>
          <p className="drawer-address">{application.display_address}</p>
          <span className={`status-label ${application.status_group.toLowerCase()}`}>{application.status_group}</span>
        </div>
        <div className="drawer-section">
          <h3>{isProperty ? 'Issue' : 'Proposal'}</h3>
          <p className="description">{application.description}</p>
        </div>
        <div className="drawer-section">
          <h3><MapPin size={17} aria-hidden="true" /> Address{application.addresses.length > 1 ? 'es' : ''}</h3>
          <ul className="address-list">
            {application.addresses.map((item) => (
              <li key={item.address}>
                {item.address}
                {item.canonical_address && item.canonical_address.toUpperCase() !== item.address.toUpperCase() && (
                  <small>City address point: {item.canonical_address}</small>
                )}
              </li>
            ))}
          </ul>
        </div>
        <div className="drawer-section">
          <h3><CalendarDays size={17} aria-hidden="true" /> {isProperty ? 'Investigation details' : 'Application details'}</h3>
          <dl className="detail-list">
            {details.map(([label, value]) => (
              <div key={label}><dt>{label}</dt><dd>{value || 'Not supplied'}</dd></div>
            ))}
          </dl>
        </div>
        {isProperty && (
          <div className="drawer-section">
            <h3><ClipboardList size={17} aria-hidden="true" /> Deficiencies <span className="heading-count">{application.deficiencies?.length || 0}</span></h3>
            {application.deficiencies?.length ? (
              <ul className="deficiency-list">
                {application.deficiencies.map((item, index) => (
                  <li key={`${index}-${item.location}-${item.text}`}>
                    <div><strong>{[item.location, item.sublocation].filter(Boolean).join(' · ') || 'Location not supplied'}</strong>{item.status && <span>{item.status}</span>}</div>
                    <p>{item.text || 'No deficiency description supplied.'}</p>
                  </li>
                ))}
              </ul>
            ) : <p className="muted">No deficiency rows are supplied for this investigation in the City dataset.</p>}
          </div>
        )}
        {!isProperty && (application.planner || application.planner_email || application.planner_phone) && (
          <div className="drawer-section">
            <h3>City contact</h3>
            <p className="planner-name">{application.planner || 'Contact not named'}</p>
            <div className="contact-links">
              {application.planner_email && <a href={`mailto:${application.planner_email}`}><Mail size={16} />{application.planner_email}</a>}
              {application.planner_phone && <a href={`tel:${application.planner_phone}`}><Phone size={16} />{application.planner_phone}</a>}
            </div>
          </div>
        )}
        <div className="drawer-actions">
          {sourceUrl ? (
            <a className="primary-button" href={sourceUrl} target="_blank" rel="noreferrer">
              {isProperty ? 'Open City investigation search' : 'Open official AIC record'} <ExternalLink size={16} />
            </a>
          ) : <p className="muted">The City feed did not provide a direct record link.</p>}
          {isProperty && <p className="source-action-note">Search the investigation number or address on the City page. The open-data feed does not provide permanent record-level links.</p>}
        </div>
      </section>
    </div>
  )
}
