import client from "./client";

export type Provider = "anthropic" | "openai" | "groq" | "ollama";

export interface MaskedKey {
  provider: string;
  masked_key: string;
}

export interface ApiKeysResponse {
  keys: MaskedKey[];
  llm_provider: string | null;
  llm_model: string | null;
  ollama_base_url: string | null;
}

export interface MessageResponse {
  message: string;
}

export async function getApiKeys(): Promise<ApiKeysResponse> {
  const { data } = await client.get<ApiKeysResponse>("/settings/api-keys");
  return data;
}

export async function saveApiKey(
  provider: Provider,
  apiKey: string,
): Promise<MessageResponse> {
  const { data } = await client.post<MessageResponse>("/settings/api-keys", {
    provider,
    api_key: apiKey,
  });
  return data;
}

export async function deleteApiKey(provider: Provider): Promise<MessageResponse> {
  const { data } = await client.delete<MessageResponse>("/settings/api-keys", {
    data: { provider },
  });
  return data;
}

export interface LlmStatusResponse {
  has_user_key: boolean;
  has_server_llm: boolean;
  server_provider: string | null;
}

export async function getLlmStatus(): Promise<LlmStatusResponse> {
  const { data } = await client.get<LlmStatusResponse>("/settings/llm-status");
  return data;
}

export async function setLlmPreference(
  provider: Provider,
  model: string,
  baseUrl?: string,
): Promise<MessageResponse> {
  const { data } = await client.put<MessageResponse>("/settings/llm-preference", {
    provider,
    model,
    base_url: baseUrl || undefined,
  });
  return data;
}

// ── Configured LLMs (unified flow) ──────────────────────────────────────────

export interface ConfiguredLlm {
  id: string;
  provider: string;
  model: string;
  base_url: string | null;
  masked_key: string | null;
  is_active: boolean;
  added_at: string;
}

export interface TestLlmResponse {
  success: boolean;
  message: string;
  response_text: string | null;
}

export interface AddLlmResponse {
  message: string;
  llm: ConfiguredLlm;
}

export interface ConfiguredLlmsResponse {
  llms: ConfiguredLlm[];
}

export async function testLlmConnection(
  provider: Provider,
  model: string,
  apiKey?: string,
  baseUrl?: string,
): Promise<TestLlmResponse> {
  const { data } = await client.post<TestLlmResponse>("/settings/test-llm", {
    provider,
    model,
    api_key: apiKey || undefined,
    base_url: baseUrl || undefined,
  });
  return data;
}

export async function getConfiguredLlms(): Promise<ConfiguredLlmsResponse> {
  const { data } = await client.get<ConfiguredLlmsResponse>("/settings/configured-llms");
  return data;
}

export async function addConfiguredLlm(
  provider: Provider,
  model: string,
  apiKey?: string,
  baseUrl?: string,
): Promise<AddLlmResponse> {
  const { data } = await client.post<AddLlmResponse>("/settings/configured-llms", {
    provider,
    model,
    api_key: apiKey || undefined,
    base_url: baseUrl || undefined,
  });
  return data;
}

export async function setActiveLlm(llmId: string): Promise<MessageResponse> {
  const { data } = await client.put<MessageResponse>("/settings/configured-llms/active", {
    llm_id: llmId,
  });
  return data;
}

export async function deleteConfiguredLlm(llmId: string): Promise<MessageResponse> {
  const { data } = await client.delete<MessageResponse>("/settings/configured-llms", {
    data: { llm_id: llmId },
  });
  return data;
}
