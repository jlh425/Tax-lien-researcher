import client from "./client";
import type { ParcelDetail, ParcelSummary, QueueStatus, ScanRequest, ScanResponse } from "../types";

export async function listParcels(params?: {
  state?: string;
  county?: string;
  instrument_type?: string;
  research_status?: string;
  min_score?: number;
  is_absentee?: boolean;
  limit?: number;
  offset?: number;
}): Promise<ParcelSummary[]> {
  const { data } = await client.get<ParcelSummary[]>("/parcels", { params });
  return data;
}

export async function getParcel(parcelId: string): Promise<ParcelDetail> {
  const { data } = await client.get<ParcelDetail>(`/parcels/${parcelId}`);
  return data;
}

export async function triggerScan(body: ScanRequest): Promise<ScanResponse> {
  const { data } = await client.post<ScanResponse>("/run", body);
  return data;
}

export async function getQueueStatus(): Promise<QueueStatus> {
  const { data } = await client.get<QueueStatus>("/queue/status");
  return data;
}
