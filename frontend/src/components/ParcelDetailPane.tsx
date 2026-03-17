import { useQuery } from "@tanstack/react-query";
import { getParcel } from "../api/parcels";
import { ScoreBadge } from "./ScoreBadge";
import { InstrumentBadge } from "./InstrumentBadge";
import type { Owner, Score, TaxLien } from "../types";

interface Props {
  parcelId: string;
  onClose: () => void;
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  if (!value && value !== 0) return null;
  return (
    <div className="flex gap-2">
      <span className="text-xs text-gray-400 w-36 flex-shrink-0">{label}</span>
      <span className="text-sm text-gray-900">{value}</span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-6">
      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">{title}</h3>
      <div className="space-y-1.5">{children}</div>
    </section>
  );
}

function fmt(n: number | null, prefix = "", suffix = ""): string {
  if (n === null || n === undefined) return "—";
  return prefix + n.toLocaleString() + suffix;
}

function pct(n: number | null): string {
  if (n === null) return "—";
  return (n * 100).toFixed(2) + "%";
}

function LienSection({ lien }: { lien: TaxLien }) {
  const isLien = lien.instrument_type === "lien_certificate";
  return (
    <div className="border border-gray-100 rounded p-3 space-y-1.5">
      <div className="flex items-center gap-2">
        <InstrumentBadge instrumentType={lien.instrument_type} />
        <span className="text-xs text-gray-500">{lien.lien_status}</span>
        {lien.certificate_number && (
          <span className="text-xs text-gray-400">#{lien.certificate_number}</span>
        )}
      </div>
      <Field label="Tax year" value={lien.tax_year} />
      <Field label="Years delinquent" value={lien.years_delinquent} />
      <Field label="Principal" value={fmt(lien.principal_amount, "$")} />
      <Field label="Total owed" value={fmt(lien.total_owed, "$")} />
      {isLien && (
        <>
          <Field label="Cert rate" value={lien.certificate_interest_rate !== null ? pct(lien.certificate_interest_rate) : null} />
          <Field label="Redemption deadline" value={lien.redemption_deadline} />
        </>
      )}
      {!isLien && (
        <>
          <Field label="Auction date" value={lien.auction_date} />
          <Field label="Auction platform" value={lien.auction_platform} />
          <Field label="Opening bid" value={fmt(lien.opening_bid, "$")} />
          <Field label="Post-sale redemption" value={lien.post_sale_redemption_days !== null ? `${lien.post_sale_redemption_days} days` : null} />
          <Field label="Title risk" value={lien.title_risk_level} />
        </>
      )}
      {lien.auction_url && (
        <a href={lien.auction_url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-500 underline">
          Auction link ↗
        </a>
      )}
    </div>
  );
}

function OwnerSection({ owner }: { owner: Owner }) {
  return (
    <div className="border border-gray-100 rounded p-3 space-y-1.5">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-gray-800">{owner.owner_of_record ?? "Unknown owner"}</span>
        {owner.owner_type && (
          <span className="text-xs bg-gray-100 text-gray-600 rounded px-1">{owner.owner_type}</span>
        )}
        {owner.is_absentee && (
          <span className="text-xs bg-orange-100 text-orange-700 rounded px-1">absentee</span>
        )}
      </div>
      {owner.mailing_address && (
        <Field label="Mailing" value={`${owner.mailing_address}${owner.mailing_city ? `, ${owner.mailing_city}` : ""}${owner.mailing_state ? ` ${owner.mailing_state}` : ""}${owner.mailing_zip ? ` ${owner.mailing_zip}` : ""}`} />
      )}
      {owner.beneficial_owner && (
        <Field
          label="Beneficial owner"
          value={`${owner.beneficial_owner} (${owner.beneficial_owner_confidence ?? "?"} confidence)`}
        />
      )}
      <Field label="Best phone" value={owner.best_phone} />
      <Field label="Best email" value={owner.best_email} />
    </div>
  );
}

function ScoreSection({ score }: { score: Score }) {
  const isLien = score.instrument_type === "lien_certificate";
  return (
    <div className="border border-gray-100 rounded p-3 space-y-1.5">
      <div className="flex items-center gap-3">
        <ScoreBadge score={score.overall_score} size="lg" />
        <span className="text-xs text-gray-400">{score.score_model_version}</span>
      </div>
      {isLien ? (
        <>
          <Field label="LTV ratio" value={score.lien_to_value_ratio !== null ? (score.lien_to_value_ratio * 100).toFixed(1) + "%" : null} />
          <Field label="Cert rate" value={score.certificate_rate !== null ? pct(score.certificate_rate) : null} />
          <Field label="Redemption urgency" value={score.redemption_urgency !== null ? `${score.redemption_urgency}/10` : null} />
          <Field label="Owner motivation" value={score.owner_motivation !== null ? `${score.owner_motivation}/10` : null} />
          <Field label="Contact reachability" value={score.contact_reachability !== null ? `${score.contact_reachability}/10` : null} />
        </>
      ) : (
        <>
          <Field label="ARV estimate" value={fmt(score.arv_estimate, "$")} />
          <Field label="Opening bid" value={fmt(score.opening_bid, "$")} />
          <Field label="ARV/bid ratio" value={score.arv_to_bid_ratio !== null ? `${score.arv_to_bid_ratio}x` : null} />
          <Field label="Title clarity" value={score.title_clarity !== null ? `${score.title_clarity}/10` : null} />
          <Field label="Condition risk" value={score.condition_risk !== null ? `${score.condition_risk}/10` : null} />
          <Field label="Competition risk" value={score.competition_risk !== null ? `${score.competition_risk}/10` : null} />
          <Field label="Redemption risk" value={score.post_sale_redemption_risk !== null ? `${score.post_sale_redemption_risk}/10` : null} />
        </>
      )}
      {score.risk_flags && score.risk_flags.length > 0 && (
        <div className="flex gap-1 flex-wrap mt-1">
          {score.risk_flags.map((f) => (
            <span key={f} className="text-xs bg-red-50 text-red-600 rounded px-1.5 py-0.5">
              {f.replace(/_/g, " ")}
            </span>
          ))}
        </div>
      )}
      {score.score_rationale && (
        <p className="text-xs text-gray-400 mt-1 leading-relaxed">{score.score_rationale}</p>
      )}
    </div>
  );
}

export function ParcelDetailPane({ parcelId, onClose }: Props) {
  const { data: parcel, isLoading, error } = useQuery({
    queryKey: ["parcel", parcelId],
    queryFn: () => getParcel(parcelId),
  });

  if (isLoading) {
    return <div className="p-10 text-center text-gray-400">Loading…</div>;
  }
  if (error || !parcel) {
    return <div className="p-10 text-center text-red-400">Failed to load parcel.</div>;
  }

  return (
    <div className="p-6 max-w-2xl">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold text-gray-900">
            {parcel.address ?? parcel.parcel_id}
          </h2>
          <p className="text-sm text-gray-500">
            {parcel.county.charAt(0).toUpperCase() + parcel.county.slice(1)} County, {parcel.state}{" "}
            · <span className="font-mono text-xs">{parcel.parcel_id}</span>
          </p>
          <div className="flex gap-2 mt-1">
            <span className="text-xs bg-gray-100 text-gray-600 rounded px-1.5 py-0.5">
              {parcel.research_status.replace(/_/g, " ")}
            </span>
            {parcel.data_freshness !== "fresh" && (
              <span className="text-xs bg-yellow-100 text-yellow-700 rounded px-1.5 py-0.5">
                {parcel.data_freshness}
              </span>
            )}
          </div>
        </div>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">
          ✕
        </button>
      </div>

      {/* Property */}
      <Section title="Property">
        <Field label="Type" value={parcel.property_type} />
        <Field label="Zoning" value={parcel.zoning} />
        <Field label="Zoning notes" value={parcel.zoning_notes} />
        <Field label="Acreage" value={parcel.acreage !== null ? `${parcel.acreage} ac` : null} />
        <Field label="Year built" value={parcel.year_built} />
        <Field label="Assessed land" value={fmt(parcel.assessed_land_val, "$")} />
        <Field label="Assessed impr." value={fmt(parcel.assessed_impr_val, "$")} />
        <Field label="Assessed total" value={fmt(parcel.assessed_total, "$")} />
        <Field label="Market value est." value={fmt(parcel.market_value_est, "$")} />
        <Field label="Last sale date" value={parcel.last_sale_date} />
        <Field label="Last sale price" value={fmt(parcel.last_sale_price, "$")} />
        {parcel.legal_description && (
          <Field label="Legal desc." value={<span className="font-mono text-xs">{parcel.legal_description}</span>} />
        )}
      </Section>

      {/* Liens / Deeds */}
      {parcel.tax_liens.length > 0 && (
        <Section title={`Liens / Deeds (${parcel.tax_liens.length})`}>
          {parcel.tax_liens.map((l) => (
            <LienSection key={l.id} lien={l} />
          ))}
        </Section>
      )}

      {/* Owners */}
      {parcel.owners.length > 0 && (
        <Section title={`Ownership (${parcel.owners.length})`}>
          {parcel.owners.map((o) => (
            <OwnerSection key={o.id} owner={o} />
          ))}
        </Section>
      )}

      {/* Scores */}
      {parcel.scores.length > 0 && (
        <Section title="Score Breakdown">
          {parcel.scores.map((s) => (
            <ScoreSection key={s.id} score={s} />
          ))}
        </Section>
      )}
    </div>
  );
}
