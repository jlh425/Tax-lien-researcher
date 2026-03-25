import client from "./client";
import type { CaseSearchResponse, CourtCase, LienSearchResponse } from "../types";

export async function searchFederalCases(params: {
  party_name: string;
  state?: string;
  case_type?: string;
}): Promise<CaseSearchResponse> {
  const { data } = await client.get<CaseSearchResponse>("/v1/court-records/cases", { params });
  return data;
}

export async function getCaseDetails(caseId: string): Promise<CourtCase> {
  const { data } = await client.get<CourtCase>(`/v1/court-records/cases/${caseId}`);
  return data;
}

export async function searchStateLiens(params: {
  debtor_name: string;
  state: string;
  lien_type?: string;
}): Promise<LienSearchResponse> {
  const { data } = await client.get<LienSearchResponse>("/v1/court-records/liens", { params });
  return data;
}
