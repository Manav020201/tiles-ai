import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";

function mockFetch(opts: { ok?: boolean; status?: number; jsonData?: unknown }) {
  return vi.fn().mockResolvedValue({
    ok: opts.ok ?? true,
    status: opts.status ?? 200,
    statusText: "",
    json: async () => opts.jsonData,
  } as Response);
}

describe("api client", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("parses a GET response", async () => {
    global.fetch = mockFetch({ jsonData: [{ id: "ask" }] }) as unknown as typeof fetch;
    const tiles = await api.listTiles();
    expect(tiles[0].id).toBe("ask");
  });

  it("throws ApiError with the server detail on non-ok", async () => {
    global.fetch = mockFetch({ ok: false, status: 404, jsonData: { detail: "no tile" } }) as unknown as typeof fetch;
    await expect(api.getTile("nope")).rejects.toBeInstanceOf(ApiError);
    await expect(api.getTile("nope")).rejects.toMatchObject({ status: 404, message: "no tile" });
  });

  it("POSTs a JSON body", async () => {
    const f = mockFetch({ jsonData: {} });
    global.fetch = f as unknown as typeof fetch;
    await api.run("ask", "hello");
    const [url, opts] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/tiles/ask/run");
    expect(opts.method).toBe("POST");
    expect(JSON.parse(opts.body as string)).toEqual({ input: "hello" });
  });

  it("clears a brain pin with a null provider", async () => {
    const f = mockFetch({ jsonData: {} });
    global.fetch = f as unknown as typeof fetch;
    await api.pinBrain("ask", null);
    const [, opts] = f.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(opts.body as string)).toEqual({ provider_id: null });
  });
});
