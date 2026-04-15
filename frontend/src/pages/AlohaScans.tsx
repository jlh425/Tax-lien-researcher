import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listScans } from "../api/scans";
import { ScanForm } from "../components/ScanForm";

function statusBadge(status: string) {
  const styles: Record<string, string> = {
    active: "bg-blue-100 text-blue-700",
    done: "bg-green-100 text-green-700",
    queued: "bg-gray-100 text-gray-600",
    failed: "bg-red-100 text-red-700",
  };
  return (
    <span className={`inline-block text-xs font-medium px-2 py-0.5 rounded ${styles[status] ?? styles.queued}`}>
      {status}
    </span>
  );
}

export function AlohaScans() {
  const [showScan, setShowScan] = useState(false);
  const { data: scans = [], isLoading, refetch } = useQuery({
    queryKey: ["scans"],
    queryFn: listScans,
    refetchInterval: 15_000,
  });

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-4xl mx-auto px-6 py-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-bold text-gray-900">Scan History</h2>
          <button
            onClick={() => setShowScan(true)}
            className="bg-blue-600 text-white text-sm font-medium px-4 py-2 rounded hover:bg-blue-700 transition"
          >
            + New Scan
          </button>
        </div>

        {isLoading ? (
          <div className="text-center text-gray-400 py-12">Loading...</div>
        ) : scans.length === 0 ? (
          <div className="text-center text-gray-400 py-12">
            No scans yet.{" "}
            <button className="text-blue-500" onClick={() => setShowScan(true)}>
              Start your first scan.
            </button>
          </div>
        ) : (
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <th className="px-4 py-3">County</th>
                  <th className="px-4 py-3">State</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Progress</th>
                  <th className="px-4 py-3">Started</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {scans.map((scan) => (
                  <tr key={scan.id} className="hover:bg-gray-50 transition">
                    <td className="px-4 py-3 font-medium text-gray-900 capitalize">
                      {scan.county}
                    </td>
                    <td className="px-4 py-3 text-gray-600">{scan.state}</td>
                    <td className="px-4 py-3">{statusBadge(scan.status)}</td>
                    <td className="px-4 py-3 text-gray-600">
                      {scan.records_found} / {scan.records_total} parcels
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs">
                      {new Date(scan.started_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

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
