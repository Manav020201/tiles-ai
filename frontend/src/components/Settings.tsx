import { useState } from "react";
import { api, ApiError } from "../api";
import type { Provider } from "../types";

// Manage the brains that power tiles: add a cloud LLM or a local (Ollama) model,
// set the default, test it, or remove it. Reachable any time from the nav bar.
export function Settings({
  providers,
  onChanged,
  onClose,
}: {
  providers: Provider[];
  onChanged: () => void;
  onClose: () => void;
}) {
  const [tests, setTests] = useState<Record<string, { ok: boolean; detail: string }>>({});
  const [busy, setBusy] = useState(false);

  // Add-brain form
  const [kind, setKind] = useState<"hosted" | "local">("hosted");
  const [provider, setProvider] = useState("anthropic");
  const [apiKey, setApiKey] = useState("");
  const [endpoint, setEndpoint] = useState("http://localhost:11434");
  const [model, setModel] = useState("claude-opus-4-8");
  const [error, setError] = useState<string | null>(null);

  const slug = model.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const canAdd = model.trim() && (kind === "local" ? endpoint.trim() : apiKey.trim());

  async function act(fn: () => Promise<unknown>) {
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
  }

  async function test(id: string) {
    const r = await api.testProvider(id);
    setTests((prev) => ({ ...prev, [id]: r }));
  }

  async function add() {
    const body =
      kind === "local"
        ? { id: slug || "local", kind: "local", endpoint: endpoint.trim(), model: model.trim() }
        : {
            id: slug || "cloud",
            kind: "hosted",
            provider,
            api_key: apiKey.trim(),
            model: model.trim(),
          };
    await act(async () => {
      await api.addProvider(body, providers.length === 0);
      setApiKey("");
    });
  }

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="grabber" />
        <div className="sheet-head">
          <div className="sheet-icon tint-instant">🧠</div>
          <div className="sheet-title">Brains</div>
        </div>
        <p className="sheet-desc">
          The model that powers your tiles. Add a cloud LLM or a local one (Ollama). Tiles use the
          default unless one pins its own.
        </p>

        {providers.length === 0 && <p className="empty">No brains yet — add one below.</p>}
        <div className="brain-rows">
          {providers.map((p) => (
            <div className="row" key={p.id}>
              <div>
                <div className="row-label">
                  {p.model} {p.is_default && <span className="pill pill-brain">default</span>}
                </div>
                <div className="row-sub">
                  {p.kind === "local" ? `local · ${p.endpoint}` : `cloud · ${p.provider}`}
                  {tests[p.id] && (
                    <span className={tests[p.id].ok ? "test-ok" : "test-error"}>
                      {" "}
                      {tests[p.id].ok ? "✓ working" : `✕ ${tests[p.id].detail}`}
                    </span>
                  )}
                </div>
              </div>
              <div className="row-actions">
                {!p.is_default && (
                  <button className="btn btn-sm" disabled={busy} onClick={() => act(() => api.setDefault(p.id))}>
                    Default
                  </button>
                )}
                <button className="btn btn-sm" disabled={busy} onClick={() => test(p.id)}>
                  Test
                </button>
                <button
                  className="btn btn-sm btn-reject"
                  disabled={busy}
                  onClick={() => act(() => api.removeProvider(p.id))}
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>

        <h3 className="settings-subhead">Add a brain</h3>
        <div className="seg">
          <button className={kind === "hosted" ? "seg-on" : ""} onClick={() => setKind("hosted")}>
            ☁️ Cloud
          </button>
          <button className={kind === "local" ? "seg-on" : ""} onClick={() => setKind("local")}>
            💻 Local
          </button>
        </div>

        {kind === "hosted" ? (
          <>
            <div className="form-grid">
              <label className="field">
                <span>Provider</span>
                <select className="select" value={provider} onChange={(e) => setProvider(e.target.value)}>
                  <option value="anthropic">Anthropic</option>
                  <option value="openai">OpenAI</option>
                </select>
              </label>
              <label className="field">
                <span>Model</span>
                <input value={model} onChange={(e) => setModel(e.target.value)} />
              </label>
            </div>
            <label className="field">
              <span>API key (stored locally only)</span>
              <input type="password" value={apiKey} placeholder="sk-…" onChange={(e) => setApiKey(e.target.value)} />
            </label>
          </>
        ) : (
          <div className="form-grid">
            <label className="field">
              <span>Endpoint</span>
              <input value={endpoint} onChange={(e) => setEndpoint(e.target.value)} />
            </label>
            <label className="field">
              <span>Model</span>
              <input value={model} placeholder="llama3" onChange={(e) => setModel(e.target.value)} />
            </label>
          </div>
        )}

        {error && <div className="error-text">{error}</div>}

        <div className="modal-actions">
          <button className="btn" onClick={onClose} disabled={busy}>
            Done
          </button>
          <button className="btn btn-primary" onClick={add} disabled={busy || !canAdd}>
            Add brain
          </button>
        </div>
      </div>
    </div>
  );
}
