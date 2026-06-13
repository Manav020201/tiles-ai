import { useState } from "react";
import { api, ApiError } from "../api";
import type { RunResponse, Tile } from "../types";

const TIER_LABEL: Record<string, string> = {
  read_only: "read only",
  draft: "draft",
  autonomous: "autonomous",
};

export function TileCard({
  tile,
  onChanged,
  onOpenSettings,
}: {
  tile: Tile;
  onChanged: () => void;
  onOpenSettings: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [lastRun, setLastRun] = useState<RunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const active = tile.state === "active";

  async function toggle() {
    setBusy(true);
    setError(null);
    try {
      if (active) await api.deactivate(tile.id);
      else await api.activate(tile.id);
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function run() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.run(tile.id, null);
      setLastRun(res);
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={`tile ${active ? "tile-active" : ""}`}>
      <button
        className="tile-gear"
        title="Brain settings"
        onClick={onOpenSettings}
      >
        ⚙
      </button>

      <button className="tile-face" onClick={toggle} disabled={busy} title={active ? "Tap to stop" : "Tap to run"}>
        <span className="tile-icon">{tile.icon}</span>
        <span className="tile-name">{tile.name}</span>
        <span className={`status-dot ${active ? "on" : "off"}`} />
      </button>

      <div className="tile-desc">{tile.description}</div>

      <div className="tile-badges">
        <span className={`pill tier-${tile.permission_tier}`}>
          {TIER_LABEL[tile.permission_tier]}
        </span>
        {tile.needs_brain ? (
          <span className="pill pill-warn">no brain</span>
        ) : (
          <span className="pill pill-brain" title={tile.brain?.label}>
            {tile.uses_default_brain ? "default" : "pinned"}: {tile.brain?.model}
          </span>
        )}
      </div>

      {active && (
        <button className="btn btn-run" onClick={run} disabled={busy}>
          Run
        </button>
      )}

      {error && <div className="tile-error">{error}</div>}

      {lastRun && (
        <div className="run-result">
          <div className="run-result-label">last run</div>
          <pre>{renderResult(lastRun)}</pre>
        </div>
      )}
    </div>
  );
}

function renderResult(run: RunResponse): string {
  const lines: string[] = [];
  if (run.result != null) {
    lines.push(typeof run.result === "string" ? run.result : JSON.stringify(run.result, null, 2));
  }
  if (run.queued.length) lines.push(`\n→ ${run.queued.length} action queued for approval`);
  if (run.executed.length) lines.push(`\n→ ${run.executed.length} action executed`);
  if (run.rejected.length) lines.push(`\n→ ${run.rejected.length} action rejected (tier)`);
  return lines.join("");
}
