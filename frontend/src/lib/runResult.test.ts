import { describe, expect, it } from "vitest";
import { renderResult } from "./runResult";
import type { RunResponse } from "../types";

const base: RunResponse = { tile_id: "x", result: null, executed: [], queued: [], rejected: [] };

describe("renderResult", () => {
  it("renders a string result verbatim", () => {
    expect(renderResult({ ...base, result: "hello" })).toBe("hello");
  });

  it("pretty-prints an object result", () => {
    expect(renderResult({ ...base, result: { a: 1 } })).toContain('"a": 1');
  });

  it("tallies queued actions", () => {
    const out = renderResult({
      ...base,
      result: "drafted",
      queued: [{ approval_id: "1", tool: "send_message", summary: "", args: {} }],
    });
    expect(out).toContain("1 action queued for approval");
  });

  it("notes tier-rejected actions", () => {
    const out = renderResult({ ...base, result: "r", rejected: [{ tool: "send_message" }] });
    expect(out).toContain("rejected (tier)");
  });
});
