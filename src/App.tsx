import { useEffect, useState } from 'react'
import { AlertTriangle, ExternalLink, Menu } from 'lucide-react'
import { AppSidebar, type View } from '@/components/AppSidebar'
import { ApplicationsView } from '@/components/ApplicationsView'
import { DigestView } from '@/components/DigestView'
import { DataView } from '@/components/DataView'
import { formatDateTime } from '@/lib/format'
import './App.css'

export default function App() {
  const data = window.__WARD5_DATA__
  const [view, setView] = useState<View>('applications')
  const [mobileOpen, setMobileOpen] = useState(false)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') setMobileOpen(false) }
    document.addEventListener('keydown', close)
    return () => document.removeEventListener('keydown', close)
  }, [])

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 15 * 60 * 1000)
    return () => window.clearInterval(timer)
  }, [])

  if (!data) {
    return (
      <main className="data-error">
        <h1>Ward 5 Development Watch</h1>
        <p>The bundled application snapshot could not be loaded. Run the refresh command in the project folder to regenerate it.</p>
        <code>python3 scripts/wardwatch.py --ward 05 --build</code>
      </main>
    )
  }

  const snapshotTime = new Date(data.generated_at).getTime()
  const isStale = !Number.isFinite(snapshotTime) || now - snapshotTime > 36 * 60 * 60 * 1000

  return (
    <div className="app-frame">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <AppSidebar view={view} onView={setView} data={data} mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
      <div className="workspace">
        <header className="workspace-header">
          <button className="icon-button mobile-menu" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu size={22} /></button>
          <div className="mobile-brand">Ward 5 Development Watch</div>
          <p>Official City data snapshot · {formatDateTime(data.generated_at)}</p>
          <a href={data.source.information_url} target="_blank" rel="noreferrer">City source <ExternalLink size={13} /></a>
        </header>
        {isStale && (
          <div className="stale-warning" role="alert">
            <AlertTriangle size={21} aria-hidden="true" />
            <div>
              <strong>This snapshot may be out of date.</strong>
              <p>Last successful update: {Number.isFinite(snapshotTime) ? formatDateTime(data.generated_at) : 'timestamp unavailable'}. The last good register remains available while the scheduled update needs attention.</p>
            </div>
          </div>
        )}
        <main id="main-content" className="main-content">
          {view === 'applications' && <ApplicationsView data={data} />}
          {view === 'digest' && <DigestView data={data} />}
          {view === 'data' && <DataView data={data} />}
        </main>
        <footer className="workspace-footer">
          <span>Ward {data.ward.number} · {data.ward.name}</span>
          <span>Contains information licensed under the Open Government Licence – Toronto.</span>
        </footer>
      </div>
    </div>
  )
}
