import type { RunResponse } from "../types";

// Render a run's result + a one-line tally of what the gate did with any
// proposed actions, for the tile sheet's "last run" panel.
export function renderResult(run: RunResponse): string {
  const lines: string[] = [];
  if (run.result != null) {
    lines.push(
      typeof run.result === "string" ? run.result : JSON.stringify(run.result, null, 2)
    );
  }
  if (run.queued.length) lines.push(`\n→ ${run.queued.length} action queued for approval`);
  if (run.executed.length) lines.push(`\n→ ${run.executed.length} action executed`);
  if (run.rejected.length) lines.push(`\n→ ${run.rejected.length} action rejected (tier)`);
  return lines.join("");
}
