/** A real-estate parcel record. */
export interface Parcel {
  id: string;
  apn: string;
  address: string;
  county: string;
  state: string;
  assessed_value: number | null;
  land_use_code: string | null;
}

/** A tax lien attached to a parcel. */
export interface TaxLien {
  id: string;
  parcel_id: string;
  lien_amount: number;
  interest_rate: number | null;
  status: "active" | "redeemed" | "foreclosed";
  sale_date: string | null;
}

/** A property owner. */
export interface Owner {
  id: string;
  name: string;
  mailing_address: string | null;
  owner_type: "individual" | "entity" | "unknown";
}

/** An investment score computed for a parcel/lien. */
export interface Score {
  id: string;
  parcel_id: string;
  overall: number;
  risk: number;
  opportunity: number;
  computed_at: string;
}
