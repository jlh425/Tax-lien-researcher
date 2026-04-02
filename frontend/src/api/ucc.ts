import client from "./client";
import type { UCCSearchResponse, UCCDetailResponse } from "../types";

export async function searchUCCFilings(params: {
  debtor_name: string;
  state: string;
  filing_type?: string;
}): Promise<UCCSearchResponse> {
  const { data } = await client.get<UCCSearchResponse>("/ucc/filings", { params });
  return data;
}

export async function getFilingDetails(
  filingNumber: string,
  state: string,
): Promise<UCCDetailResponse> {
  const { data } = await client.get<UCCDetailResponse>(
    `/ucc/filings/${encodeURIComponent(filingNumber)}`,
    { params: { state } },
  );
  return data;
}
