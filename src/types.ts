export type Category = 'planning' | 'coa' | 'tlab' | 'property'

export interface Address {
  address: string
  canonical_address?: string | null
  latitude: number | null
  longitude: number | null
}

export interface Deficiency {
  location: string | null
  sublocation: string | null
  text: string | null
  status: string | null
}

export interface Application {
  id: string
  application_number: string
  reference_file: string | null
  folder_name: string | null
  folder_type: string | null
  type_description: string | null
  category: Category
  category_label: string
  status: string
  status_group: string
  record_status: string | null
  submitted_date: string | null
  completed_date: string | null
  latest_milestone: string | null
  latest_milestone_date: string | null
  hearing_date: string | null
  community_meeting_date: string | null
  last_modified_date: string | null
  description: string
  planner: string | null
  planner_email: string | null
  planner_phone: string | null
  aic_url: string | null
  source_url?: string | null
  investigation_id?: string | null
  investigation_type?: string | null
  issue?: string | null
  notice_or_order_date?: string | null
  next_inspection?: string | null
  expiry_date?: string | null
  deficiencies?: Deficiency[]
  deficiency_summary?: string | null
  ward_number: string | null
  ward_name: string | null
  addresses: Address[]
  display_address: string
  first_seen: string
  last_seen: string
  is_new?: boolean
}

export interface RecordChange {
  field: string
  label: string
  before: string | number | null
  after: string | number | null
}

export interface Digest {
  digest_date: string
  captured_at: string
  previous_captured_at: string | null
  baseline: boolean
  property_baseline?: boolean
  new_applications: Application[]
  changes: { application: Application; changes: RecordChange[] }[]
  submitted_today: Application[]
  counts: {
    address_rows: number
    applications: number
    open_applications: number
    property_investigations?: number
    new: number
    changed: number
  }
}

export interface DashboardData {
  generated_at: string
  ward: { number: string; name: string }
  source: {
    name: string
    layer_url: string
    information_url: string
    address_rows: number
    applications?: number
    coverage: string[]
    note: string
  }
  property_source: {
    name: string
    package_url: string
    information_url: string
    address_points_url: string
    source_investigations: number
    source_address_rows: number
    ward_investigations: number
    matched_address_rows: number
    nonmatched_address_rows: number
    ambiguous_address_rows: number
    investigations_with_deficiencies: number
    deficiency_rows: number
    included_types: string[]
    note: string
  }
  stats: {
    applications: number
    aic_applications?: number
    property_records?: number
    open: number
    closed: number
    planning: number
    coa: number
    tlab: number
    property: number
    new: number
    changed: number
  }
  applications: Application[]
  latest_digest: Digest
  recent_digests: Digest[]
  downloads: {
    all_csv: string
    latest_digest_html: string
    latest_digest_json: string
  }
}

declare global {
  interface Window {
    __WARD5_DATA__?: DashboardData
  }
}
