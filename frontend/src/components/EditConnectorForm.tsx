import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { Connector, ConnectorTool } from "../types";

// Edit or remove a connected app from the board: rename it, change the MCP
// command/env, re-fetch its tools, or delete it (refused while tiles use it).
export function EditConnectorForm({
  connectorId,
  onClose,
  onChanged,
}: {
  connectorId: string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [conn, setConn] = useState<Connector | null>(null);
  const [app, setApp] = useState("");
  const [endpoint, setEndpoint] = useState("");
  const [envText, setEnvText] = useState("");
  const [tools, setTools] = useState<ConnectorTool[]>([]);
  const [fetching, setFetching] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listConnectors().then((all) => {
      const c = all.find((x) => x.id === connectorId);
      if (!c) return;
      setConn(c);
      setApp(c.app);
      setEndpoint(c.endpoint ?? "");
      setEnvText((c.env ?? []).join(", "));
      setTools(c.tools);
    });
  }, [connectorId]);

  const env = envText.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean);
  const isMcp = conn?.kind === "mcp";

  async function refetch() {
    setFetching(true);
    setError(null);
    try {
      setTools(await api.introspectConnector(endpoint.trim(), env));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setFetching(false);
    }
  }

  function toggle(name: string) {
    setTools((prev) => prev.map((t) => (t.name === name ? { ...t, side_effect: !t.side_effect } : t)));
  }

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await api.updateConnector(connectorId, {
        app: app.trim(),
        endpoint: isMcp ? endpoint.trim() : undefined,
        env,
        tools,
      });
      onChanged();
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm(`Disconnect "${app || connectorId}"? This removes its files.`)) return;
    setBusy(true);
    setError(null);
    try {
      await api.removeConnector(connectorId);
      onChanged();
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
      setBusy(false);
    }
  }

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="grabber" />
        <div className="sheet-head">
          <div className="sheet-icon tint-draft">🔌</div>
          <div className="sheet-title">Edit {conn?.app ?? connectorId}</div>
        </div>
        <p className="sheet-desc">Edit the connection, re-read its tools, or disconnect it.</p>

        {!conn ? (
          <p className="empty">Loading…</p>
        ) : (
          <>
            <label className="field">
              <span>App name</span>
              <input value={app} onChange={(e) => setApp(e.target.value)} />
            </label>
            {isMcp && (
              <>
                <label className="field">
                  <span>MCP server command</span>
                  <input value={endpoint} onChange={(e) => setEndpoint(e.target.value)} />
                </label>
                <label className="field">
                  <span>Required env vars (comma-separated)</span>
                  <input value={envText} onChange={(e) => setEnvText(e.target.value)} />
                </label>
                <button className="btn btn-full" onClick={refetch} disabled={fetching}>
                  {fetching ? "Launching server…" : "Re-fetch tools"}
                </button>
              </>
            )}
            <div className="field" style={{ marginTop: "0.8rem" }}>
              <span>Tools — checked ones write</span>
              <div className="tool-list">
                {tools.map((t) => (
                  <label key={t.name} className="tool-check">
                    <input type="checkbox" checked={t.side_effect} onChange={() => toggle(t.name)} />
                    <span>
                      {t.name}
                      {t.side_effect && <span className="pill pill-warn">writes</span>}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          </>
        )}

        {error && <div className="error-text">{error}</div>}

        <div className="modal-actions modal-actions-split">
          <button className="btn btn-plain btn-danger" onClick={remove} disabled={busy || !conn}>
            Disconnect
          </button>
          <div className="modal-actions-right">
            <button className="btn" onClick={onClose} disabled={busy}>
              Cancel
            </button>
            <button className="btn btn-primary" onClick={save} disabled={busy || !conn || !app.trim()}>
              {busy ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
