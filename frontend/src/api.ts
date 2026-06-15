// Thin typed client over the control-plane REST API. Native fetch, no deps.

import type {
  Approval,
  Connector,
  NewTile,
  Provider,
  RunResponse,
  Tile,
  TileDetail,
} from "./types";

async function http<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: body !== undefined ? { "content-type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new ApiError(res.status, (detail as { detail?: string }).detail ?? res.statusText);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export const api = {
  listTiles: () => http<Tile[]>("GET", "/api/tiles"),
  getTile: (id: string) => http<TileDetail>("GET", `/api/tiles/${id}`),
  listConnectors: () => http<Connector[]>("GET", "/api/connectors"),
  createTile: (body: NewTile) => http<Tile>("POST", "/api/tiles", body),
  activate: (id: string) => http<Tile>("POST", `/api/tiles/${id}/activate`),
  deactivate: (id: string) => http<Tile>("POST", `/api/tiles/${id}/deactivate`),
  run: (id: string, input: unknown) => http<RunResponse>("POST", `/api/tiles/${id}/run`, { input }),
  pinBrain: (id: string, providerId: string | null) =>
    http<Tile>("PUT", `/api/tiles/${id}/brain`, { provider_id: providerId }),

  listApprovals: () => http<Approval[]>("GET", "/api/approvals"),
  resolveApproval: (id: string, approved: boolean) =>
    http<Approval>("POST", `/api/approvals/${id}/resolve`, { approved }),

  listProviders: () => http<Provider[]>("GET", "/api/providers"),
  addProvider: (provider: Record<string, unknown>, makeDefault: boolean) =>
    http<Provider[]>("POST", "/api/providers", { provider, make_default: makeDefault }),
  setDefault: (providerId: string) =>
    http<Provider[]>("PUT", "/api/brain/default", { provider_id: providerId }),
  testProvider: (id: string) => http<{ ok: boolean; detail: string }>("POST", `/api/providers/${id}/test`),
};
