import client from "./client";

export interface ScanHistoryItem {
  id: string;
  state: string;
  county: string;
  status: "active" | "done" | "queued" | "failed";
  records_found: number;
  records_total: number;
  started_at: string;
  completed_at: string | null;
}

export interface ScanHistoryResponse {
  scans: ScanHistoryItem[];
}

export async function listScans(): Promise<ScanHistoryItem[]> {
  const { data } = await client.get<ScanHistoryResponse>("/scans");
  return data.scans;
}

export async function getScan(scanId: string): Promise<ScanHistoryItem> {
  const { data } = await client.get<ScanHistoryItem>(`/scans/${scanId}`);
  return data;
}
