/** Lightweight parcel card (list view). */
export interface ParcelSummary {
  parcel_id: string;
  state: string;
  county: string;
  address: string | null;
  property_type: string | null;
  zoning: string | null;
  acreage: number | null;
  assessed_total: number | null;
  research_status: string;
  data_freshness: string;
  latitude: number | null;
  longitude: number | null;
  // Denormalised from lien
  instrument_type: string | null;
  lien_status: string | null;
  total_owed: number | null;
  redemption_deadline: string | null;
  auction_date: string | null;
  // Denormalised from score
  overall_score: number | null;
  risk_flags: string[] | null;
}

/** Full lien / deed record. */
export interface TaxLien {
  id: number;
  instrument_type: string;
  lien_status: string;
  tax_year: number | null;
  years_delinquent: number | null;
  principal_amount: number;
  interest_amount: number | null;
  penalty_amount: number | null;
  total_owed: number | null;
  filing_date: string | null;
  redemption_deadline: string | null;
  certificate_number: string | null;
  certificate_interest_rate: number | null;
  auction_date: string | null;
  auction_platform: string | null;
  auction_url: string | null;
  opening_bid: number | null;
  post_sale_redemption_days: number | null;
  title_risk_level: string | null;
  source_url: string | null;
  retrieved_at: string;
}

/** Owner record. */
export interface Owner {
  id: number;
  owner_of_record: string | null;
  owner_type: string | null;
  mailing_address: string | null;
  mailing_city: string | null;
  mailing_state: string | null;
  mailing_zip: string | null;
  is_absentee: boolean | null;
  deed_type: string | null;
  beneficial_owner: string | null;
  beneficial_owner_confidence: string | null;
  best_phone: string | null;
  best_email: string | null;
  research_depth: number;
}

/** Score record. */
export interface Score {
  id: number;
  instrument_type: string;
  overall_score: number | null;
  score_model_version: string | null;
  property_potential: number | null;
  risk_score: number | null;
  lien_to_value_ratio: number | null;
  certificate_rate: number | null;
  redemption_urgency: number | null;
  owner_motivation: number | null;
  contact_reachability: number | null;
  arv_estimate: number | null;
  opening_bid: number | null;
  arv_to_bid_ratio: number | null;
  title_clarity: number | null;
  condition_risk: number | null;
  competition_risk: number | null;
  post_sale_redemption_risk: number | null;
  risk_flags: string[] | null;
  score_rationale: string | null;
  scored_at: string;
}

/** Full parcel detail. */
export interface ParcelDetail {
  parcel_id: string;
  user_id: string | null;
  state: string;
  county: string;
  address: string | null;
  address_normalized: string | null;
  legal_description: string | null;
  acreage: number | null;
  land_use_code: string | null;
  property_type: string | null;
  zoning: string | null;
  zoning_notes: string | null;
  assessed_land_val: number | null;
  assessed_impr_val: number | null;
  assessed_total: number | null;
  market_value_est: number | null;
  last_sale_date: string | null;
  last_sale_price: number | null;
  year_built: number | null;
  latitude: number | null;
  longitude: number | null;
  research_status: string;
  data_freshness: string;
  last_crawled_at: string | null;
  created_at: string;
  updated_at: string;
  tax_liens: TaxLien[];
  owners: Owner[];
  scores: Score[];
}

/** Queue status response. */
export interface QueueStatus {
  pending: number;
  processing: number;
  failed: number;
  complete: number;
  agents: Record<string, number>;
}

/** Scan request. */
export interface ScanRequest {
  state: string;
  county: string;
  instrument_filter?: string | null;
  max_records?: number;
}

/** Scan response. */
export interface ScanResponse {
  status: string;
  state: string;
  county: string;
  records_found: number;
  enqueued: number;
  message: string;
}
