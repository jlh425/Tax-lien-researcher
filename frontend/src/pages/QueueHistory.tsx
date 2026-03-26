import { useQuery } from "@tanstack/react-query";
import { getQueueStatus } from "../api/parcels";

export function QueueHistory() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["queue-status"],
    queryFn: getQueueStatus,
    refetchInterval: 5000,
  });

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Queue History</h1>
        <a href="/" className="text-sm text-blue-600 hover:underline">
          Back to Dashboard
        </a>
      </div>

      {isError && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded p-3 mb-4 text-sm">
          Failed to load queue status.
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <StatusCard
          label="Pending"
          count={data?.pending ?? 0}
          color="yellow"
          loading={isLoading}
        />
        <StatusCard
          label="Processing"
          count={data?.processing ?? 0}
          color="blue"
          loading={isLoading}
        />
        <StatusCard
          label="Complete"
          count={data?.complete ?? 0}
          color="green"
          loading={isLoading}
        />
        <StatusCard
          label="Failed"
          count={data?.failed ?? 0}
          color="red"
          loading={isLoading}
        />
      </div>

      {/* Agent Breakdown */}
      <section className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Agent Breakdown</h2>
        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-8 bg-gray-100 rounded animate-pulse" />
            ))}
          </div>
        ) : data?.agents && Object.keys(data.agents).length > 0 ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b border-gray-100">
                <th className="pb-2 font-medium">Agent</th>
                <th className="pb-2 font-medium text-right">Tasks</th>
                <th className="pb-2 font-medium text-right">Share</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.agents)
                .sort(([, a], [, b]) => b - a)
                .map(([agent, count]) => {
                  const total = Object.values(data.agents).reduce((s, n) => s + n, 0);
                  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
                  return (
                    <tr key={agent} className="border-b border-gray-50">
                      <td className="py-2 font-medium text-gray-800">{agent}</td>
                      <td className="py-2 text-right text-gray-600">{count}</td>
                      <td className="py-2 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <div className="w-16 h-2 bg-gray-100 rounded overflow-hidden">
                            <div
                              className="h-full bg-blue-500 rounded"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                          <span className="text-gray-400 text-xs w-8 text-right">{pct}%</span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        ) : (
          <p className="text-gray-400 text-sm">No agent activity yet.</p>
        )}
      </section>
    </div>
  );
}

function StatusCard({
  label,
  count,
  color,
  loading,
}: {
  label: string;
  count: number;
  color: "yellow" | "blue" | "green" | "red";
  loading: boolean;
}) {
  const colorMap = {
    yellow: "bg-yellow-50 text-yellow-700 border-yellow-200",
    blue: "bg-blue-50 text-blue-700 border-blue-200",
    green: "bg-green-50 text-green-700 border-green-200",
    red: "bg-red-50 text-red-700 border-red-200",
  };

  return (
    <div className={`rounded-lg border p-4 ${colorMap[color]}`}>
      <p className="text-xs font-medium uppercase tracking-wide opacity-70">{label}</p>
      {loading ? (
        <div className="h-8 w-12 bg-gray-200 rounded animate-pulse mt-1" />
      ) : (
        <p className="text-2xl font-bold mt-1">{count.toLocaleString()}</p>
      )}
    </div>
  );
}
