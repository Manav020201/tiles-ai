import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { FlowRun, Provider, RunResponse, Tile, TilesEvent } from "../types";
import { renderResult } from "../lib/runResult";

function prettify(id: string): string {
  return id.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const EVENT_LABEL: Record<string, string> = {
  "tile.activated": "activated",
  "tile.deactivated": "stopped",
  "tile.run": "ran",
  "action.executed": "executed",
  "action.queued": "queued",
  "action.rejected": "rejected",
  "approval.resolved": "approval resolved",
};

function fmtTime(ts: number | null): string {
  return ts ? new Date(ts * 1000).toLocaleTimeString() : "";
}

// The "app view": a bottom sheet to run a tile and tune it. Holds the activate
// toggle (green = running), input + Run, the last result, and the brain picker.
export function TileSheet({
  tile,
  providers,
  events,
  onClose,
  onChanged,
  onEdit,
}: {
  tile: Tile;
  providers: Provider[];
  events: TilesEvent[];
  onClose: () => void;
  onChanged: () => void;
  onEdit: () => void;
}) {
  const tileEvents = events.filter((e) => e.tile_id === tile.id).slice(0, 8);
  const [feeds, setFeeds] = useState<string[]>([]);
  const [flowRun, setFlowRun] = useState<FlowRun | null>(null);

  useEffect(() => {
    api.tileFlow(tile.id).then((f) => setFeeds(f.feeds)).catch(() => setFeeds([]));
  }, [tile.id]);
  const [busy, setBusy] = useState(false);
  const [input, setInput] = useState("");
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [lastRun, setLastRun] = useState<RunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const active = tile.state === "active";
  const blocked = !tile.connector_ready && !active;
  const tint = tile.connector === null ? "tint-instant" : `tint-${tile.permission_tier}`;
  const needsInput = tile.wants_input && !tile.input_optional;
  const runDisabled = busy || (needsInput && input.trim().length === 0);

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

  async function runChain(consumerId: string) {
    setBusy(true);
    setError(null);
    try {
      setFlowRun(await api.runFlow([tile.id, consumerId], tile.wants_input ? input : null));
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function saveKeys() {
    if (!tile.connector) return;
    const values = Object.fromEntries(Object.entries(keys).filter(([, v]) => v.trim()));
    if (Object.keys(values).length === 0) return;
    setBusy(true);
    setError(null);
    try {
      await api.setConnectorSecrets(tile.connector, values);
      setKeys({});
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
          {tile.schedule && <span className="pill pill-tool">⏱ every {tile.schedule}</span>}
        </div>

        {blocked && (
          <div className="notice">
            <div>This tile needs an API key to run:</div>
            {tile.missing_env.map((name) => (
              <input
                key={name}
                type="password"
                autoComplete="off"
                className="key-input"
                placeholder={`paste ${name}`}
                value={keys[name] ?? ""}
                onChange={(e) => setKeys((k) => ({ ...k, [name]: e.target.value }))}
              />
            ))}
            <button className="btn btn-full" onClick={saveKeys} disabled={busy}>
              {busy ? "Saving…" : "Save key"}
            </button>
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
            placeholder={(tile.input_hint ?? "Input…") + (tile.input_optional ? " (optional)" : "")}
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

        {feeds.length > 0 && (
          <div className="chain">
            <div className="result-label">Chain — run this, then feed it into:</div>
            <div className="chain-btns">
              {feeds.map((f) => (
                <button
                  key={f}
                  className="btn chain-btn"
                  onClick={() => runChain(f)}
                  disabled={runDisabled}
                >
                  → {prettify(f)}
                </button>
              ))}
            </div>
            {flowRun && (
              <pre className="chain-result">
                {flowRun.steps
                  .map(
                    (s) =>
                      `${prettify(s.tile_id)}: ${
                        typeof s.result === "string" ? s.result : JSON.stringify(s.result)
                      }${s.queued ? ` (→ ${s.queued} queued)` : ""}`
                  )
                  .join("\n\n")}
              </pre>
            )}
          </div>
        )}

        {tileEvents.length > 0 && (
          <div className="tile-activity">
            <div className="result-label">Recent activity</div>
            <ul className="feed">
              {tileEvents.map((e, i) => (
                <li key={i} className="feed-item">
                  <span className="feed-time">{fmtTime(e.ts)}</span>
                  <span className="feed-label">{EVENT_LABEL[e.type] ?? e.type}</span>
                  {typeof e.data.tool === "string" && (
                    <span className="pill pill-tool">{e.data.tool}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

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
