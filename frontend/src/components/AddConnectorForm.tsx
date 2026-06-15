import { useState } from "react";
import { api, ApiError } from "../api";
import type { ConnectorTool } from "../types";

// Connect a new application: point at its MCP server command, fetch its tools
// automatically, and scaffold a connector. It then shows up in the New Tile form.
export function AddConnectorForm({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [app, setApp] = useState("");
  const [endpoint, setEndpoint] = useState("npx -y ");
  const [envText, setEnvText] = useState("");
  const [tools, setTools] = useState<ConnectorTool[] | null>(null);
  const [fetching, setFetching] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const env = envText
    .split(/[,\s]+/)
    .map((s) => s.trim())
    .filter(Boolean);

  async function fetchTools() {
    setFetching(true);
    setError(null);
    try {
      setTools(await api.introspectConnector(endpoint.trim(), env));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
      setTools(null);
    } finally {
      setFetching(false);
    }
  }

  function toggleSideEffect(name: string) {
    setTools(
      (prev) =>
        prev?.map((t) => (t.name === name ? { ...t, side_effect: !t.side_effect } : t)) ?? null
    );
  }

  async function create() {
    setBusy(true);
    setError(null);
    try {
      await api.createConnector({
        app: app.trim(),
        kind: "mcp",
        endpoint: endpoint.trim(),
        env,
        tools: tools ?? [],
      });
      onCreated();
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="grabber" />
        <div className="sheet-head">
          <div className="sheet-icon tint-draft">🔌</div>
          <div className="sheet-title">Connect an app</div>
        </div>
        <p className="sheet-desc">
          Point at the app's MCP server. We'll read its tools, then your tiles can use them.
        </p>

        <label className="field">
          <span>App name</span>
          <input value={app} placeholder="GitHub" onChange={(e) => setApp(e.target.value)} />
        </label>

        <label className="field">
          <span>MCP server command</span>
          <input
            value={endpoint}
            placeholder="npx -y @modelcontextprotocol/server-github"
            onChange={(e) => setEndpoint(e.target.value)}
          />
        </label>

        <label className="field">
          <span>Required env vars (comma-separated, optional)</span>
          <input
            value={envText}
            placeholder="GITHUB_PERSONAL_ACCESS_TOKEN"
            onChange={(e) => setEnvText(e.target.value)}
          />
        </label>

        <button
          className="btn btn-full"
          onClick={fetchTools}
          disabled={fetching || endpoint.trim().length < 4}
        >
          {fetching ? "Launching server…" : "Fetch tools"}
        </button>

        {tools && (
          <div className="field" style={{ marginTop: "0.9rem" }}>
            <span>
              {tools.length} tool{tools.length === 1 ? "" : "s"} — check the ones that write
            </span>
            <div className="tool-list">
              {tools.map((t) => (
                <label key={t.name} className="tool-check">
                  <input
                    type="checkbox"
                    checked={t.side_effect}
                    onChange={() => toggleSideEffect(t.name)}
                  />
                  <span>
                    {t.name}
                    {t.side_effect && <span className="pill pill-warn">writes</span>}
                  </span>
                </label>
              ))}
            </div>
          </div>
        )}

        {error && <div className="error-text">{error}</div>}

        <div className="modal-actions">
          <button className="btn" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button
            className="btn btn-primary"
            onClick={create}
            disabled={busy || app.trim().length === 0 || endpoint.trim().length < 4}
          >
            {busy ? "Connecting…" : "Connect app"}
          </button>
        </div>
      </div>
    </div>
  );
}
