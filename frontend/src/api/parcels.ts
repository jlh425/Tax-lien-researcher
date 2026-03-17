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
  const { data } = await client.get<ParcelSummary[]>("/v1/parcels", { params });
  return data;
}

export async function getParcel(parcelId: string): Promise<ParcelDetail> {
  const { data } = await client.get<ParcelDetail>(`/v1/parcels/${parcelId}`);
  return data;
}

export async function triggerScan(body: ScanRequest): Promise<ScanResponse> {
  const { data } = await client.post<ScanResponse>("/v1/run", body);
  return data;
}

export async function getQueueStatus(): Promise<QueueStatus> {
  const { data } = await client.get<QueueStatus>("/v1/queue/status");
  return data;
}
