import { Building2, Database, FileClock, Files, ExternalLink, X } from 'lucide-react'
import type { DashboardData } from '@/types'
import { formatDateTime } from '@/lib/format'

export type View = 'applications' | 'digest' | 'data'

interface Props {
  view: View
  onView: (view: View) => void
  data: DashboardData
  mobileOpen: boolean
  onClose: () => void
}

const navigation: { id: View; label: string; icon: typeof Files }[] = [
  { id: 'applications', label: 'Record register', icon: Files },
  { id: 'digest', label: 'Daily digest', icon: FileClock },
  { id: 'data', label: 'Data & automation', icon: Database },
]

export function AppSidebar({ view, onView, data, mobileOpen, onClose }: Props) {
  return (
    <>
      {mobileOpen && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={onClose} />}
      <aside className={`app-sidebar ${mobileOpen ? 'is-open' : ''}`} aria-label="Main navigation">
        <div className="brand-block">
          <Building2 aria-hidden="true" size={25} strokeWidth={1.6} />
          <div><strong>Ward 5</strong><span>Development Watch</span></div>
          <button className="icon-button sidebar-close" onClick={onClose} aria-label="Close navigation"><X size={20} /></button>
        </div>
        <div className="ward-caption">York South–Weston<br />Toronto, Ontario</div>
        <nav className="sidebar-nav">
          {navigation.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              className={view === id ? 'active' : ''}
              aria-current={view === id ? 'page' : undefined}
              onClick={() => { onView(id); onClose() }}
            >
              <Icon size={18} aria-hidden="true" />
              <span>{label}</span>
              {id === 'digest' && data.stats.new > 0 && <span className="nav-count">{data.stats.new}</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-source">
          <div className="live-label"><span className="status-dot" />Official City source</div>
          <p>{data.stats.aic_applications ?? data.stats.applications} AIC applications and {data.stats.property_records ?? 0} Property Standards investigations.</p>
          <p>Snapshot: {formatDateTime(data.generated_at)}</p>
          <a href={data.source.information_url} target="_blank" rel="noreferrer">
            About the City AIC <ExternalLink size={13} aria-hidden="true" />
          </a>
        </div>
      </aside>
    </>
  )
}
