import { useState } from "react";
import { api } from "../api";
import type { Provider, Tile } from "../types";

// The brain-override panel: pin a tile to a specific provider, or fall back to
// the global default. Mirrors the spec's "Brain: using default — change".
export function TileSettings({
  tile,
  providers,
  onClose,
  onChanged,
}: {
  tile: Tile;
  providers: Provider[];
  onClose: () => void;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  // "" represents "use default"; otherwise a provider id.
  const initial = tile.uses_default_brain ? "" : findPinnedId(tile, providers);
  const [selection, setSelection] = useState<string>(initial);

  async function save() {
    setBusy(true);
    try {
      await api.pinBrain(tile.id, selection === "" ? null : selection);
      onChanged();
      onClose();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2 className="modal-title">
          {tile.icon} {tile.name} — Brain
        </h2>
        <p className="modal-sub">
          Choose which configured brain this tile runs on. Applies on next activation.
        </p>

        <label className="field">
          <span>Brain</span>
          <select value={selection} onChange={(e) => setSelection(e.target.value)}>
            <option value="">Use default</option>
            {providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.id} — {p.model} {p.is_default ? "(default)" : ""}
              </option>
            ))}
          </select>
        </label>

        <div className="modal-actions">
          <button className="btn" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={save} disabled={busy}>
            Save
          </button>
        </div>
      </div>
    </div>
  );
}

// Best-effort match of the tile's resolved brain back to a configured provider id.
function findPinnedId(tile: Tile, providers: Provider[]): string {
  if (!tile.brain) return "";
  const match = providers.find((p) => p.model === tile.brain!.model);
  return match?.id ?? "";
}
