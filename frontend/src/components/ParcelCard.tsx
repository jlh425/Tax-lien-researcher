import type { ParcelSummary } from "../types";
import { ScoreBadge } from "./ScoreBadge";
import { InstrumentBadge } from "./InstrumentBadge";

interface Props {
  parcel: ParcelSummary;
  selected: boolean;
  onClick: () => void;
}

function fmt(n: number | null, prefix = ""): string {
  if (n === null) return "—";
  return prefix + n.toLocaleString();
}

function daysUntil(dateStr: string | null): string {
  if (!dateStr) return "";
  const days = Math.round((new Date(dateStr).getTime() - Date.now()) / 86_400_000);
  if (days < 0) return "expired";
  if (days === 0) return "today";
  return `${days}d`;
}

export function ParcelCard({ parcel, selected, onClick }: Props) {
  const deadline = parcel.redemption_deadline ?? parcel.auction_date;
  const deadlineDays = daysUntil(deadline);
  const isUrgent = deadline && daysUntil(deadline) !== "" && parseInt(deadlineDays) <= 30;

  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-4 py-3 border-b border-gray-100 hover:bg-blue-50 transition-colors ${
        selected ? "bg-blue-50 border-l-2 border-l-blue-500" : ""
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          {/* Address */}
          <p className="text-sm font-medium text-gray-900 truncate">
            {parcel.address ?? parcel.parcel_id}
          </p>
          <p className="text-xs text-gray-500 truncate">
            {parcel.county.charAt(0).toUpperCase() + parcel.county.slice(1)} Co., {parcel.state}
            {parcel.property_type && ` · ${parcel.property_type}`}
          </p>
        </div>
        <ScoreBadge score={parcel.overall_score} size="sm" />
      </div>

      <div className="flex items-center gap-2 mt-1.5 flex-wrap">
        <InstrumentBadge instrumentType={parcel.instrument_type} />

        {parcel.total_owed !== null && (
          <span className="text-xs text-gray-600 font-medium">
            ${parcel.total_owed.toLocaleString()}
          </span>
        )}

        {deadline && (
          <span className={`text-xs ${isUrgent ? "text-red-600 font-semibold" : "text-gray-400"}`}>
            {parcel.redemption_deadline ? "Redeem" : "Auction"}: {deadlineDays}
          </span>
        )}

        {parcel.assessed_total !== null && (
          <span className="text-xs text-gray-400">
            AV: {fmt(parcel.assessed_total, "$")}
          </span>
        )}
      </div>

      {parcel.risk_flags && parcel.risk_flags.length > 0 && (
        <div className="mt-1 flex gap-1 flex-wrap">
          {parcel.risk_flags.slice(0, 3).map((flag) => (
            <span key={flag} className="text-xs bg-red-50 text-red-600 rounded px-1">
              {flag.replace(/_/g, " ")}
            </span>
          ))}
        </div>
      )}
    </button>
  );
}
