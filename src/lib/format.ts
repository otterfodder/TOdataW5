import type { Application, Category } from '@/types'

export function formatDate(value: string | null | undefined, options?: Intl.DateTimeFormatOptions) {
  if (!value) return 'Not supplied'
  const date = new Date(value.includes('T') ? value : `${value}T00:00:00Z`)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('en-CA', options ?? {
    year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC',
  }).format(date)
}

export function formatDateTime(value: string) {
  const date = new Date(value)
  return new Intl.DateTimeFormat('en-CA', {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: 'numeric', minute: '2-digit', timeZone: 'America/Toronto',
  }).format(date) + ' Toronto time'
}

export const categoryNames: Record<Category | 'all', string> = {
  all: 'All categories',
  planning: 'Planning',
  coa: 'C of A',
  tlab: 'TLAB',
  property: 'Property Standards',
}

function csvCell(value: unknown) {
  let text = value == null ? '' : String(value)
  if (/^[\s]*[=+\-@]/.test(text)) text = `'${text}`
  return `"${text.replaceAll('"', '""')}"`
}

export function exportApplications(applications: Application[], ward: string) {
  const headings = [
    'Application number', 'Category', 'Application type', 'Status group', 'Status',
    'Submitted date', 'Addresses', 'Description', 'Latest milestone', 'Hearing date',
    'Community meeting date', 'Planner', 'Planner email', 'Planner phone', 'Investigation ID',
    'Notice or order date', 'Next inspection', 'Expiry date', 'Issue', 'Deficiencies', 'Official source URL',
  ]
  const rows = applications.map((app) => [
    app.application_number, app.category_label, app.type_description, app.status_group,
    app.status, app.submitted_date, app.addresses.map((item) => item.address).join('; '),
    app.description, app.latest_milestone, app.hearing_date, app.community_meeting_date,
    app.planner, app.planner_email, app.planner_phone, app.investigation_id,
    app.notice_or_order_date, app.next_inspection, app.expiry_date, app.issue,
    app.deficiency_summary, app.source_url || app.aic_url,
  ])
  const csv = [headings, ...rows].map((row) => row.map(csvCell).join(',')).join('\r\n')
  const blob = new Blob(['﻿', csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `ward-${ward}-filtered-applications.csv`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
