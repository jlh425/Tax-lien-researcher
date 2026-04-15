import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listParcels } from "../api/parcels";
import { ParcelCard } from "../components/ParcelCard";
import { ParcelDetailPane } from "../components/ParcelDetailPane";
import { ScanForm } from "../components/ScanForm";

type InstrumentFilter = "" | "lien_certificate" | "tax_deed";
type SortKey = "score" | "total_owed" | "deadline";

export function AlohaLiens() {
  const { parcelId: deepLinkId } = useParams<{ parcelId: string }>();
  const [selectedId, setSelectedId] = useState<string | null>(deepLinkId ?? null);
  const [instrumentFilter, setInstrumentFilter] = useState<InstrumentFilter>("");
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [showScan, setShowScan] = useState(false);

  const { data: parcels = [], isLoading, refetch } = useQuery({
    queryKey: ["parcels", { instrument_type: instrumentFilter || undefined }],
    queryFn: () =>
      listParcels({
        instrument_type: instrumentFilter || undefined,
        limit: 200,
      }),
  });

  // Client-side sort
  const sorted = [...parcels].sort((a, b) => {
    if (sortKey === "score") return (b.overall_score ?? 0) - (a.overall_score ?? 0);
    if (sortKey === "total_owed") return (b.total_owed ?? 0) - (a.total_owed ?? 0);
    // deadline — soonest first
    const da = a.redemption_deadline ?? a.auction_date ?? "9999";
    const db = b.redemption_deadline ?? b.auction_date ?? "9999";
    return da.localeCompare(db);
  });

  const lienCount = parcels.filter((p) => p.instrument_type === "lien_certificate").length;
  const deedCount = parcels.filter((p) => p.instrument_type === "tax_deed").length;

  return (
    <>
      {/* Filter bar */}
      <div className="bg-white border-b border-gray-100 px-6 py-2 flex items-center gap-3 text-sm">
        <div className="flex gap-1">
          {(["", "lien_certificate", "tax_deed"] as InstrumentFilter[]).map((f) => (
            <button
              key={f}
              onClick={() => setInstrumentFilter(f)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition ${
                instrumentFilter === f
                  ? "bg-blue-100 text-blue-700"
                  : "text-gray-500 hover:bg-gray-100"
              }`}
            >
              {f === "" ? "All" : f === "lien_certificate" ? "Lien Cert" : "Tax Deed"}
            </button>
          ))}
        </div>

        <select
          value={sortKey}
          onChange={(e) => setSortKey(e.target.value as SortKey)}
          className="border border-gray-200 rounded px-2 py-1 text-xs text-gray-600"
        >
          <option value="score">Sort: Score</option>
          <option value="total_owed">Sort: Amount</option>
          <option value="deadline">Sort: Deadline</option>
        </select>

        <span className="ml-auto text-xs text-gray-400">
          {parcels.length} opportunities
          {lienCount > 0 && <> &middot; {lienCount} lien certs</>}
          {deedCount > 0 && <> &middot; {deedCount} tax deeds</>}
        </span>

        <button
          onClick={() => setShowScan(true)}
          className="bg-blue-600 text-white text-xs font-medium px-3 py-1.5 rounded hover:bg-blue-700 transition"
        >
          + New Scan
        </button>
      </div>

      {/* Split pane */}
      <div className="flex flex-1 overflow-hidden">
        {/* Card list */}
        <div className="w-96 flex-shrink-0 overflow-y-auto border-r border-gray-200 bg-white">
          {isLoading ? (
            <div className="p-8 text-center text-gray-400">Loading...</div>
          ) : sorted.length === 0 ? (
            <div className="p-8 text-center text-gray-400">
              No parcels found.{" "}
              <button className="text-blue-500" onClick={() => setShowScan(true)}>
                Start a scan.
              </button>
            </div>
          ) : (
            sorted.map((p) => (
              <ParcelCard
                key={p.parcel_id}
                parcel={p}
                selected={selectedId === p.parcel_id}
                onClick={() => setSelectedId(p.parcel_id)}
              />
            ))
          )}
        </div>

        {/* Detail pane */}
        <div className="flex-1 overflow-y-auto">
          {selectedId ? (
            <ParcelDetailPane parcelId={selectedId} onClose={() => setSelectedId(null)} />
          ) : (
            <div className="flex items-center justify-center h-full text-gray-400">
              Select a parcel to view details
            </div>
          )}
        </div>
      </div>

      {/* Scan modal */}
      {showScan && (
        <ScanForm
          onClose={() => setShowScan(false)}
          onSuccess={() => {
            setShowScan(false);
            refetch();
          }}
        />
      )}
    </>
  );
}
