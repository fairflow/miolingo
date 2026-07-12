// HTTP client tier for the phonetics oracle sidecar. Every function throws
// OracleError on non-2xx so callers degrade explicitly (status badge, hidden
// features) rather than rendering half-truths.

import type { G2pResponse, MaterialsIndex, OracleHealth } from './types.js';

export class OracleError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'OracleError';
  }
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new OracleError(res.status, `${url} → ${res.status}`);
  return res.json() as Promise<T>;
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new OracleError(res.status, `${url} → ${res.status}`);
  return res.json() as Promise<T>;
}

export function health(): Promise<OracleHealth> {
  return getJson('/api/health');
}

export function g2p(texts: string[], lang: string): Promise<G2pResponse> {
  return postJson('/api/g2p', { texts, lang });
}

export function materialsIndex(): Promise<MaterialsIndex> {
  return getJson('/api/materials');
}
