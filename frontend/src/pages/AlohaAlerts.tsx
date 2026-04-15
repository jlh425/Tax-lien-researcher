import { useQuery } from "@tanstack/react-query";
import { listParcels } from "../api/parcels";
import { ScoreBadge } from "../components/ScoreBadge";
import { InstrumentBadge } from "../components/InstrumentBadge";

function daysUntil(dateStr: string | null): number | null {
  if (!dateStr) return null;
  return Math.round((new Date(dateStr).getTime() - Date.now()) / 86_400_000);
}

type AlertLevel = "urgent" | "warning" | "info";

interface Alert {
  parcelId: string;
  address: string;
  county: string;
  state: string;
  instrumentType: string | null;
  score: number | null;
  level: AlertLevel;
  message: string;
  daysLeft: number;
}

function alertBadge(level: AlertLevel) {
  const styles: Record<AlertLevel, string> = {
    urgent: "bg-red-100 text-red-700",
    warning: "bg-yellow-100 text-yellow-700",
    info: "bg-blue-100 text-blue-700",
  };
  return (
    <span className={`inline-block text-xs font-medium px-2 py-0.5 rounded ${styles[level]}`}>
      {level}
    </span>
  );
}

export function AlohaAlerts() {
  const { data: parcels = [], isLoading } = useQuery({
    queryKey: ["parcels", {}],
    queryFn: () => listParcels({ limit: 500 }),
  });

  // Build alerts from parcels with approaching deadlines
  const alerts: Alert[] = [];
  for (const p of parcels) {
    const deadline = p.redemption_deadline ?? p.auction_date;
    const days = daysUntil(deadline);
    if (days === null) continue;
    if (days > 90) continue;

    const deadlineType = p.redemption_deadline ? "Redemption" : "Auction";
    let level: AlertLevel = "info";
    let message = `${deadlineType} deadline in ${days} days`;

    if (days <= 0) {
      level = "urgent";
      message = `${deadlineType} deadline has passed`;
    } else if (days <= 30) {
      level = "urgent";
      message = `${deadlineType} deadline in ${days} days — action required`;
    } else if (days <= 90) {
      level = "warning";
    }

    alerts.push({
      parcelId: p.parcel_id,
      address: p.address ?? p.parcel_id,
      county: p.county,
      state: p.state,
      instrumentType: p.instrument_type,
      score: p.overall_score,
      level,
      message,
      daysLeft: days,
    });
  }

  // Sort: urgent first, then by days remaining
  alerts.sort((a, b) => {
    const levelOrder: Record<AlertLevel, number> = { urgent: 0, warning: 1, info: 2 };
    const ld = levelOrder[a.level] - levelOrder[b.level];
    if (ld !== 0) return ld;
    return a.daysLeft - b.daysLeft;
  });

  const urgentCount = alerts.filter((a) => a.level === "urgent").length;
  const warningCount = alerts.filter((a) => a.level === "warning").length;

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-4xl mx-auto px-6 py-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-bold text-gray-900">Deadline Alerts</h2>
          <span className="text-xs text-gray-400">
            {urgentCount > 0 && (
              <span className="text-red-600 font-medium mr-3">{urgentCount} urgent</span>
            )}
            {warningCount > 0 && (
              <span className="text-yellow-600 font-medium">{warningCount} warnings</span>
            )}
          </span>
        </div>

        {isLoading ? (
          <div className="text-center text-gray-400 py-12">Loading...</div>
        ) : alerts.length === 0 ? (
          <div className="text-center text-gray-400 py-12">
            No upcoming deadlines within 90 days.
          </div>
        ) : (
          <div className="space-y-3">
            {alerts.map((alert) => (
              <a
                key={alert.parcelId}
                href={`/aloha/liens/${alert.parcelId}`}
                className="block bg-white rounded-lg border border-gray-200 p-4 hover:border-blue-300 transition"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      {alertBadge(alert.level)}
                      <InstrumentBadge instrumentType={alert.instrumentType} />
                      <ScoreBadge score={alert.score} size="sm" />
                    </div>
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {alert.address}
                    </p>
                    <p className="text-xs text-gray-500">
                      {alert.county.charAt(0).toUpperCase() + alert.county.slice(1)} Co., {alert.state}
                    </p>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className={`text-sm font-semibold ${
                      alert.level === "urgent" ? "text-red-600" : "text-gray-600"
                    }`}>
                      {alert.daysLeft <= 0 ? "Expired" : `${alert.daysLeft}d`}
                    </p>
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-2">{alert.message}</p>
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
