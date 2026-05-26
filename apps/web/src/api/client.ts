import type { CheckRecord, PromptVersionStats, ReviewLabel, ScoreResponse } from "../lib/types";

const baseUrl = (): string =>
  (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

async function asJson<T>(r: Response): Promise<T> {
  if (!r.ok) {
    const body = await r.text().catch(() => "");
    throw new Error(`request failed: ${r.status} ${body}`);
  }
  return (await r.json()) as T;
}

export async function fetchRecent(limit = 50): Promise<CheckRecord[]> {
  const r = await fetch(`${baseUrl()}/v1/checks/recent?limit=${limit}`);
  return asJson<CheckRecord[]>(r);
}

export async function fetchQueue(): Promise<CheckRecord[]> {
  const r = await fetch(`${baseUrl()}/v1/queue`);
  return asJson<CheckRecord[]>(r);
}

export async function reviewCheck(id: string, label: ReviewLabel): Promise<CheckRecord> {
  const r = await fetch(`${baseUrl()}/v1/checks/${id}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label }),
  });
  return asJson<CheckRecord>(r);
}

export async function fetchStats(): Promise<PromptVersionStats[]> {
  const r = await fetch(`${baseUrl()}/v1/prompt-versions/stats`);
  return asJson<PromptVersionStats[]>(r);
}

export async function evaluate(
  promptVersion: string,
  outputText: string,
): Promise<ScoreResponse> {
  const r = await fetch(`${baseUrl()}/v1/evaluate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt_version: promptVersion, output_text: outputText, context: {} }),
  });
  return asJson<ScoreResponse>(r);
}

export function wsUrl(): string {
  const base = baseUrl();
  return base.replace(/^http/, "ws") + "/v1/live";
}
