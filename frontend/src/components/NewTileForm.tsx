import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { Connector } from "../types";

// Create a tile from the board: fill a form, and the backend scaffolds the
// folder (manifest + handler) and the new tile appears on the board.
export function NewTileForm({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [name, setName] = useState("");
  const [icon, setIcon] = useState("🔲");
  const [description, setDescription] = useState("");
  const [instructions, setInstructions] = useState("");
  const [tier, setTier] = useState("read_only");
  const [wantsInput, setWantsInput] = useState(true);
  const [connectorId, setConnectorId] = useState("");
  const [allowed, setAllowed] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listConnectors().then(setConnectors).catch(() => setConnectors([]));
  }, []);

  const connector = connectors.find((c) => c.id === connectorId) ?? null;

  function toggleTool(tool: string) {
    setAllowed((prev) => (prev.includes(tool) ? prev.filter((t) => t !== tool) : [...prev, tool]));
  }

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await api.createTile({
        name: name.trim(),
        icon: icon.trim() || "🔲",
        description: description.trim() || "A tile I made.",
        instructions: instructions.trim() || "You are a helpful assistant.",
        permission_tier: tier,
        connector: connectorId || null,
        allowed_tools: connectorId ? allowed : [],
        wants_input: wantsInput,
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
          <div className="sheet-icon tint-instant">{icon || "🔲"}</div>
          <div className="sheet-title">New tile</div>
        </div>
        <p className="sheet-desc">
          Describe your agent. We'll scaffold it — then edit the files to go deeper.
        </p>

        <div className="form-grid">
          <label className="field">
            <span>Name</span>
            <input value={name} placeholder="My Tile" onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="field field-narrow">
            <span>Icon</span>
            <input value={icon} onChange={(e) => setIcon(e.target.value)} maxLength={4} />
          </label>
        </div>

        <label className="field">
          <span>Description</span>
          <input
            value={description}
            placeholder="One line shown on the board"
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>

        <label className="field">
          <span>Instructions (the agent's role)</span>
          <textarea
            className="sheet-input"
            rows={3}
            value={instructions}
            placeholder="You are a helpful assistant that…"
            onChange={(e) => setInstructions(e.target.value)}
          />
        </label>

        <div className="form-grid">
          <label className="field">
            <span>Permission</span>
            <select className="select" value={tier} onChange={(e) => setTier(e.target.value)}>
              <option value="read_only">read only</option>
              <option value="draft">draft (queues for approval)</option>
              <option value="autonomous">autonomous</option>
            </select>
          </label>
          <label className="field">
            <span>App</span>
            <select
              className="select"
              value={connectorId}
              onChange={(e) => {
                setConnectorId(e.target.value);
                setAllowed([]);
              }}
            >
              <option value="">None (instant tile)</option>
              {connectors.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.app}
                </option>
              ))}
            </select>
          </label>
        </div>

        {connector && (
          <div className="field">
            <span>Tools this tile may use</span>
            <div className="tool-list">
              {connector.tools.map((t) => (
                <label key={t.name} className="tool-check">
                  <input
                    type="checkbox"
                    checked={allowed.includes(t.name)}
                    onChange={() => toggleTool(t.name)}
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

        <label className="tool-check">
          <input
            type="checkbox"
            checked={wantsInput}
            onChange={(e) => setWantsInput(e.target.checked)}
          />
          <span>Takes typed input</span>
        </label>

        {error && <div className="error-text">{error}</div>}

        <div className="modal-actions">
          <button className="btn" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button
            className="btn btn-primary"
            onClick={submit}
            disabled={busy || name.trim().length === 0}
          >
            {busy ? "Creating…" : "Create tile"}
          </button>
        </div>
      </div>
    </div>
  );
}
