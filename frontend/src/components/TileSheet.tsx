import { useState } from "react";
import { api, ApiError } from "../api";
import type { Provider, RunResponse, Tile } from "../types";
import { renderResult } from "../lib/runResult";

// The "app view": a bottom sheet to run a tile and tune it. Holds the activate
// toggle (green = running), input + Run, the last result, and the brain picker.
export function TileSheet({
  tile,
  providers,
  onClose,
  onChanged,
  onEdit,
}: {
  tile: Tile;
  providers: Provider[];
  onClose: () => void;
  onChanged: () => void;
  onEdit: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [input, setInput] = useState("");
  const [lastRun, setLastRun] = useState<RunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const active = tile.state === "active";
  const blocked = !tile.connector_ready && !active;
  const tint = tile.connector === null ? "tint-instant" : `tint-${tile.permission_tier}`;
  const runDisabled = busy || (tile.wants_input && input.trim().length === 0);

  function wrap<T>(fn: () => Promise<T>) {
    return async () => {
      setBusy(true);
      setError(null);
      try {
        await fn();
        onChanged();
      } catch (e) {
        setError(e instanceof ApiError ? e.message : String(e));
      } finally {
        setBusy(false);
      }
    };
  }

  const toggle = wrap(async () => {
    if (active) await api.deactivate(tile.id);
    else await api.activate(tile.id);
  });

  async function run() {
    setBusy(true);
    setError(null);
    try {
      setLastRun(await api.run(tile.id, tile.wants_input ? input : null));
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const pinnedId = tile.uses_default_brain
    ? ""
    : providers.find((p) => p.model === tile.brain?.model)?.id ?? "";

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="grabber" />

        <div className="sheet-head">
          <div className={`sheet-icon ${tint}`}>{tile.icon}</div>
          <div>
            <div className="sheet-title">{tile.name}</div>
          </div>
        </div>
        <p className="sheet-desc">{tile.description}</p>

        <div className="sheet-badges">
          <span className={`pill tier-${tile.permission_tier}`}>
            {tile.permission_tier.replace("_", " ")}
          </span>
          {tile.needs_brain ? (
            <span className="pill pill-warn">no brain</span>
          ) : (
            <span className="pill pill-brain">
              {tile.uses_default_brain ? "default" : "pinned"}: {tile.brain?.model}
            </span>
          )}
        </div>

        {blocked && (
          <div className="notice">
            Set {tile.missing_env.join(", ")} in your environment to enable this tile.
          </div>
        )}

        <div className="row">
          <div>
            <div className="row-label">Running</div>
            <div className="row-sub">{active ? "Green — active" : "Tap to start"}</div>
          </div>
          <label className="switch">
            <input
              type="checkbox"
              checked={active}
              disabled={busy || blocked}
              onChange={toggle}
            />
            <span className="track" />
            <span className="knob" />
          </label>
        </div>

        {active && tile.wants_input && (
          <textarea
            className="sheet-input"
            rows={3}
            value={input}
            placeholder={tile.input_hint ?? "Input…"}
            onChange={(e) => setInput(e.target.value)}
          />
        )}

        {active && (
          <button className="btn btn-primary btn-full" onClick={run} disabled={runDisabled}>
            {busy ? "Running…" : "Run"}
          </button>
        )}

        {error && <div className="error-text">{error}</div>}

        {lastRun && (
          <div className="result">
            <div className="result-label">Last run</div>
            <pre>{renderResult(lastRun)}</pre>
          </div>
        )}

        <div className="row" style={{ marginTop: "1rem" }}>
          <div className="row-label">Brain</div>
          <select
            className="select"
            value={pinnedId}
            disabled={busy}
            onChange={(e) =>
              wrap(() => api.pinBrain(tile.id, e.target.value || null))()
            }
          >
            <option value="">Default</option>
            {providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.model}
                {p.is_default ? " (default)" : ""}
              </option>
            ))}
          </select>
        </div>

        <div className="sheet-foot">
          <button className="btn btn-plain" onClick={onEdit}>
            Edit tile
          </button>
          <button className="btn btn-plain" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
