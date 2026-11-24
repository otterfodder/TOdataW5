import { useMemo, useState } from 'react'
import { ArrowUpRight, ChevronLeft, ChevronRight, Download, Search } from 'lucide-react'
import type { Application, Category, DashboardData } from '@/types'
import { categoryNames, exportApplications, formatDate } from '@/lib/format'
import { ApplicationDetail } from './ApplicationDetail'

const PAGE_SIZE = 25
type StatusFilter = 'open' | 'closed' | 'all'
type SortOrder = 'newest' | 'oldest' | 'address' | 'modified'

export function ApplicationsView({ data }: { data: DashboardData }) {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState<Category | 'all'>('all')
  const [status, setStatus] = useState<StatusFilter>('open')
  const [type, setType] = useState('all')
  const [sort, setSort] = useState<SortOrder>('newest')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<Application | null>(null)

  const types = useMemo(() => Array.from(new Set(
    data.applications.map((app) => app.type_description).filter(Boolean) as string[]
  )).sort(), [data.applications])

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return data.applications.filter((app) => {
      if (category !== 'all' && app.category !== category) return false
      if (status !== 'all' && app.status_group.toLowerCase() !== status) return false
      if (type !== 'all' && app.type_description !== type) return false
      if (needle) {
        const haystack = [
          app.application_number, app.display_address, app.description, app.planner,
          app.type_description, app.status, app.investigation_id, app.deficiency_summary,
          ...app.addresses.map((item) => item.address),
        ].join(' ').toLowerCase()
        if (!haystack.includes(needle)) return false
      }
      return true
    }).sort((a, b) => {
      if (sort === 'address') return a.display_address.localeCompare(b.display_address)
      if (sort === 'modified') return (b.last_modified_date || '').localeCompare(a.last_modified_date || '')
      const comparison = (a.submitted_date || '').localeCompare(b.submitted_date || '')
      return sort === 'oldest' ? comparison : -comparison
    })
  }, [data.applications, query, category, status, type, sort])

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const hasFilters = query || category !== 'all' || status !== 'open' || type !== 'all' || sort !== 'newest'
  const reset = () => {
    setQuery(''); setCategory('all'); setStatus('open'); setType('all'); setSort('newest'); setPage(1)
  }

  return (
    <>
      <section className="page-heading">
        <div>
          <p className="eyebrow">City of Toronto · Ward {data.ward.number}</p>
          <h1>Ward 5 record register</h1>
          <p>Current Community Planning, Committee of Adjustment, TLAB, and Property Standards records for {data.ward.name}.</p>
        </div>
        <button className="primary-button export-button" onClick={() => exportApplications(filtered, data.ward.number)}>
          <Download size={17} aria-hidden="true" /> Export {filtered.length} record{filtered.length === 1 ? '' : 's'}
        </button>
      </section>

      <section className="stats-strip" aria-label="Open application summary">
        <div><strong>{data.stats.open}</strong><span>Open records</span></div>
        <div><strong>{data.stats.planning}</strong><span>Community Planning</span></div>
        <div><strong>{data.stats.coa}</strong><span>Committee of Adjustment</span></div>
        <div><strong>{data.stats.tlab}</strong><span>TLAB</span></div>
        <div><strong>{data.stats.property}</strong><span>Property Standards</span></div>
      </section>

      <section className="register-section" aria-label="Search applications">
        <div className="search-row">
          <label className="search-field">
            <Search size={19} aria-hidden="true" />
            <span className="sr-only">Search applications</span>
            <input
              value={query}
              onChange={(event) => { setQuery(event.target.value); setPage(1) }}
              placeholder="Search address, file, proposal, deficiency, or planner…"
              type="search"
            />
          </label>
          <label className="select-field">
            <span>Status</span>
            <select value={status} onChange={(event) => { setStatus(event.target.value as StatusFilter); setPage(1) }}>
              <option value="open">Open only</option>
              <option value="closed">Recently closed</option>
              <option value="all">Open + closed</option>
            </select>
          </label>
        </div>
        <div className="filter-row">
          <div className="category-tabs" aria-label="Application category">
            {(['all', 'planning', 'coa', 'tlab', 'property'] as const).map((item) => (
              <button key={item} className={category === item ? 'active' : ''} onClick={() => { setCategory(item); setPage(1) }}>
                {categoryNames[item]}
              </button>
            ))}
          </div>
          <label className="compact-select">
            <span className="sr-only">Application type</span>
            <select value={type} onChange={(event) => { setType(event.target.value); setPage(1) }}>
              <option value="all">All application types</option>
              {types.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label className="compact-select">
            <span className="sr-only">Sort applications</span>
            <select value={sort} onChange={(event) => { setSort(event.target.value as SortOrder); setPage(1) }}>
              <option value="newest">Newest submitted / opened</option>
              <option value="oldest">Oldest submitted / opened</option>
              <option value="modified">Recently modified</option>
              <option value="address">Address A–Z</option>
            </select>
          </label>
        </div>
        <div className="results-meta">
          <p aria-live="polite"><strong>{filtered.length}</strong> record{filtered.length === 1 ? '' : 's'} found</p>
          {hasFilters && <button className="text-button" onClick={reset}>Reset filters</button>}
        </div>

        {visible.length > 0 ? (
          <>
            <div className="application-table-wrap">
              <table className="application-table">
                <thead><tr><th>Record</th><th>Address</th><th>Type</th><th>Submitted / opened</th><th>Status</th><th><span className="sr-only">View</span></th></tr></thead>
                <tbody>
                  {visible.map((app) => (
                    <tr key={app.id} onClick={() => setSelected(app)}>
                      <td>
                        <button className="record-link" onClick={() => setSelected(app)}>{app.application_number}</button>
                        <span className={`category-text ${app.category}`}>{categoryNames[app.category]}</span>
                      </td>
                      <td>{app.display_address}{app.addresses.length > 1 && <span className="address-count">+{app.addresses.length - 1} additional address{app.addresses.length - 1 === 1 ? '' : 'es'}</span>}</td>
                      <td>{app.type_description}</td>
                      <td className="date-cell">{formatDate(app.submitted_date)}</td>
                      <td><span className={`status-label ${app.status_group.toLowerCase()}`}>{app.status_group}</span><span className="status-detail">{app.status}</span></td>
                      <td><button className="row-open" onClick={() => setSelected(app)} aria-label={`View ${app.application_number}`}><ArrowUpRight size={18} /></button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="application-mobile-list">
              {visible.map((app) => (
                <button className="mobile-record" key={app.id} onClick={() => setSelected(app)}>
                  <span className={`category-text ${app.category}`}>{categoryNames[app.category]} · {app.type_description}</span>
                  <strong>{app.application_number}</strong>
                  <span>{app.display_address}</span>
                  <span className="mobile-record-meta">{formatDate(app.submitted_date)} · {app.status}</span>
                  <ArrowUpRight size={18} aria-hidden="true" />
                </button>
              ))}
            </div>
            {pages > 1 && (
              <nav className="pagination" aria-label="Application pages">
                <button className="text-button" disabled={page === 1} onClick={() => setPage((value) => value - 1)}><ChevronLeft size={17} />Previous</button>
                <span>Page {page} of {pages}</span>
                <button className="text-button" disabled={page === pages} onClick={() => setPage((value) => value + 1)}>Next<ChevronRight size={17} /></button>
              </nav>
            )}
          </>
        ) : (
          <div className="empty-state">
            <h2>No records match</h2>
            <p>Try a different address or broaden the category, type, or status filters.</p>
            <button className="secondary-button" onClick={reset}>Reset all filters</button>
          </div>
        )}
      </section>
      {selected && <ApplicationDetail application={selected} onClose={() => setSelected(null)} />}
    </>
  )
}
