import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { TileDetail } from "../types";

// Edit a tile's declarative fields from the board (name, icon, description,
// instructions, tier, input). The handler's logic stays in handler.py.
export function EditTileForm({
  tileId,
  onClose,
  onSaved,
}: {
  tileId: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [detail, setDetail] = useState<TileDetail | null>(null);
  const [name, setName] = useState("");
  const [icon, setIcon] = useState("🔲");
  const [description, setDescription] = useState("");
  const [instructions, setInstructions] = useState("");
  const [tier, setTier] = useState("read_only");
  const [wantsInput, setWantsInput] = useState(true);
  const [schedule, setSchedule] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getTile(tileId).then((d) => {
      setDetail(d);
      setName(d.name);
      setIcon(d.icon);
      setDescription(d.description);
      setInstructions(d.instructions);
      setTier(d.permission_tier);
      setWantsInput(d.wants_input);
      setSchedule(d.schedule ?? "");
    });
  }, [tileId]);

  async function remove() {
    if (!window.confirm(`Delete the tile "${detail?.name ?? tileId}"? This removes its files.`))
      return;
    setBusy(true);
    setError(null);
    try {
      await api.removeTile(tileId);
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
      setBusy(false);
    }
  }

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await api.updateTile(tileId, {
        name: name.trim(),
        icon: icon.trim() || "🔲",
        description: description.trim(),
        instructions: instructions.trim(),
        permission_tier: tier,
        wants_input: wantsInput,
        schedule: schedule.trim(),
      });
      onSaved();
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
          <div className="sheet-title">Edit {detail?.name ?? tileId}</div>
        </div>
        <p className="sheet-desc">
          Edit the manifest. The handler's logic lives in <code>handler.py</code>.
          {detail?.connector && ` Bound to ${detail.connector}.`}
        </p>

        {!detail ? (
          <p className="empty">Loading…</p>
        ) : (
          <>
            <div className="form-grid">
              <label className="field">
                <span>Name</span>
                <input value={name} onChange={(e) => setName(e.target.value)} />
              </label>
              <label className="field field-narrow">
                <span>Icon</span>
                <input value={icon} maxLength={4} onChange={(e) => setIcon(e.target.value)} />
              </label>
            </div>
            <label className="field">
              <span>Description</span>
              <input value={description} onChange={(e) => setDescription(e.target.value)} />
            </label>
            <label className="field">
              <span>Instructions (the agent's role)</span>
              <textarea
                className="sheet-input"
                rows={3}
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
              />
            </label>
            <label className="field">
              <span>Permission</span>
              <select className="select" value={tier} onChange={(e) => setTier(e.target.value)}>
                <option value="read_only">read only</option>
                <option value="draft">draft (queues for approval)</option>
                <option value="autonomous">autonomous</option>
              </select>
            </label>
            <div className="form-grid">
              <label className="tool-check" style={{ alignSelf: "end", paddingBottom: "0.6rem" }}>
                <input
                  type="checkbox"
                  checked={wantsInput}
                  onChange={(e) => setWantsInput(e.target.checked)}
                />
                <span>Takes typed input</span>
              </label>
              <label className="field">
                <span>Run every (blank = manual)</span>
                <input
                  value={schedule}
                  placeholder="e.g. 5m, 1h"
                  onChange={(e) => setSchedule(e.target.value)}
                />
              </label>
            </div>
          </>
        )}

        {error && <div className="error-text">{error}</div>}

        <div className="modal-actions modal-actions-split">
          <button className="btn btn-plain btn-danger" onClick={remove} disabled={busy || !detail}>
            Delete
          </button>
          <div className="modal-actions-right">
            <button className="btn" onClick={onClose} disabled={busy}>
              Cancel
            </button>
            <button
              className="btn btn-primary"
              onClick={save}
              disabled={busy || !detail || !name.trim()}
            >
              {busy ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
