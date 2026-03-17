import { useQuery } from "@tanstack/react-query";
import { getQueueStatus } from "../api/parcels";

export function QueueStatusBar() {
  const { data } = useQuery({
    queryKey: ["queue-status"],
    queryFn: getQueueStatus,
    refetchInterval: 10_000,
  });

  if (!data) return null;

  const { pending, processing, failed } = data;
  const total = pending + processing;

  if (total === 0 && failed === 0) return null;

  return (
    <div className="flex items-center gap-2 text-xs text-gray-500">
      {processing > 0 && (
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
          {processing} processing
        </span>
      )}
      {pending > 0 && <span>{pending} queued</span>}
      {failed > 0 && <span className="text-red-500">{failed} failed</span>}
    </div>
  );
}
