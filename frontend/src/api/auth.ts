import client from "./client";

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  tier: string;
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const { data } = await client.post<TokenResponse>("/auth/login", { email, password });
  return data;
}

export async function register(
  email: string,
  password: string,
  name?: string,
): Promise<TokenResponse> {
  const { data } = await client.post<TokenResponse>("/auth/register", {
    email,
    password,
    name: name || undefined,
  });
  return data;
}
