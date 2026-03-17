import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listParcels } from "../api/parcels";
import { ParcelCard } from "../components/ParcelCard";
import { ParcelDetailPane } from "../components/ParcelDetailPane";
import { ScanForm } from "../components/ScanForm";
import { QueueStatusBar } from "../components/QueueStatusBar";
import type { ParcelSummary } from "../types";

export function Dashboard() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filters, setFilters] = useState<{
    state?: string;
    county?: string;
    instrument_type?: string;
    min_score?: number;
  }>({});
  const [showScan, setShowScan] = useState(false);

  const { data: parcels = [], isLoading, refetch } = useQuery({
    queryKey: ["parcels", filters],
    queryFn: () => listParcels({ ...filters, limit: 200 }),
  });

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">
          Aloha <span className="text-blue-600">Tax Research</span>
        </h1>
        <div className="flex gap-3 items-center">
          <QueueStatusBar />
          <button
            onClick={() => setShowScan(true)}
            className="bg-blue-600 text-white text-sm font-medium px-4 py-2 rounded hover:bg-blue-700 transition"
          >
            + New Scan
          </button>
        </div>
      </header>

      {/* Filter bar */}
      <div className="bg-white border-b border-gray-100 px-6 py-2 flex gap-4 text-sm">
        <FilterInput
          label="State"
          value={filters.state ?? ""}
          onChange={(v) => setFilters((f) => ({ ...f, state: v || undefined }))}
          placeholder="e.g. FL"
          maxLength={2}
        />
        <FilterInput
          label="County"
          value={filters.county ?? ""}
          onChange={(v) => setFilters((f) => ({ ...f, county: v || undefined }))}
          placeholder="e.g. orange"
        />
        <select
          className="border border-gray-200 rounded px-2 py-1 text-sm"
          value={filters.instrument_type ?? ""}
          onChange={(e) =>
            setFilters((f) => ({ ...f, instrument_type: e.target.value || undefined }))
          }
        >
          <option value="">All instruments</option>
          <option value="lien_certificate">Lien Certificate</option>
          <option value="tax_deed">Tax Deed</option>
        </select>
        <FilterInput
          label="Min score"
          value={filters.min_score?.toString() ?? ""}
          onChange={(v) =>
            setFilters((f) => ({ ...f, min_score: v ? parseInt(v) : undefined }))
          }
          placeholder="0–100"
          type="number"
        />
        <button
          onClick={() => setFilters({})}
          className="text-gray-400 hover:text-gray-600 text-xs"
        >
          Clear
        </button>
        <span className="ml-auto text-gray-400 text-xs self-center">
          {parcels.length} results
        </span>
      </div>

      {/* Main area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Card list */}
        <div className="w-96 flex-shrink-0 overflow-y-auto border-r border-gray-200 bg-white">
          {isLoading ? (
            <div className="p-8 text-center text-gray-400">Loading…</div>
          ) : parcels.length === 0 ? (
            <div className="p-8 text-center text-gray-400">
              No parcels found.{" "}
              <button className="text-blue-500" onClick={() => setShowScan(true)}>
                Start a scan.
              </button>
            </div>
          ) : (
            parcels.map((p) => (
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
    </div>
  );
}

function FilterInput({
  label,
  value,
  onChange,
  placeholder,
  maxLength,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  maxLength?: number;
  type?: string;
}) {
  return (
    <label className="flex items-center gap-1 text-gray-500">
      <span className="text-xs font-medium">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        maxLength={maxLength}
        className="border border-gray-200 rounded px-2 py-1 text-sm w-24 focus:outline-none focus:ring-1 focus:ring-blue-400"
      />
    </label>
  );
}
