import { useState } from "react";
import { triggerScan } from "../api/parcels";

interface Props {
  onClose: () => void;
  onSuccess: () => void;
}

export function ScanForm({ onClose, onSuccess }: Props) {
  const [state, setState] = useState("");
  const [county, setCounty] = useState("");
  const [instrumentFilter, setInstrumentFilter] = useState("");
  const [maxRecords, setMaxRecords] = useState("5000");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await triggerScan({
        state: state.toUpperCase(),
        county: county.toLowerCase(),
        instrument_filter: instrumentFilter || null,
        max_records: parseInt(maxRecords) || 5000,
      });
      setResult(res.message || `Scan queued for ${res.state}/${res.county}`);
      setTimeout(() => {
        onSuccess();
      }, 2000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Scan failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-gray-900">New Discovery Scan</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">✕</button>
        </div>

        {result ? (
          <div className="text-center py-6">
            <p className="text-green-600 font-medium">{result}</p>
            <p className="text-xs text-gray-400 mt-1">Returning to dashboard…</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                State <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={state}
                onChange={(e) => setState(e.target.value)}
                placeholder="e.g. FL"
                maxLength={2}
                required
                className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                County <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={county}
                onChange={(e) => setCounty(e.target.value)}
                placeholder="e.g. orange"
                required
                className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Instrument filter
              </label>
              <select
                value={instrumentFilter}
                onChange={(e) => setInstrumentFilter(e.target.value)}
                className="w-full border border-gray-200 rounded px-3 py-2 text-sm"
              >
                <option value="">All (lien cert + tax deed)</option>
                <option value="lien_certificate">Lien certificates only</option>
                <option value="tax_deed">Tax deeds only</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Max records
              </label>
              <input
                type="number"
                value={maxRecords}
                onChange={(e) => setMaxRecords(e.target.value)}
                min="1"
                max="50000"
                className="w-full border border-gray-200 rounded px-3 py-2 text-sm"
              />
            </div>

            {error && (
              <p className="text-red-500 text-sm">{error}</p>
            )}

            <div className="flex gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 border border-gray-200 text-gray-600 text-sm rounded py-2 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading || !state || !county}
                className="flex-1 bg-blue-600 text-white text-sm font-medium rounded py-2 hover:bg-blue-700 disabled:opacity-50 transition"
              >
                {loading ? "Starting…" : "Start Scan"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
