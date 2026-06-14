import type { Tile } from "../types";

// A home-screen app icon: squircle + label, with a running dot when active and a
// lock when its connector needs credentials. Tapping opens the tile sheet.
export function TileIcon({ tile, onOpen }: { tile: Tile; onOpen: () => void }) {
  const active = tile.state === "active";
  const blocked = !tile.connector_ready && !active;
  const tint = tile.connector === null ? "tint-instant" : `tint-${tile.permission_tier}`;

  return (
    <div className="app-cell">
      <button
        className={`app-icon ${tint} ${active ? "is-active" : ""} ${blocked ? "is-blocked" : ""}`}
        onClick={onOpen}
        title={tile.name}
      >
        {tile.icon}
        {active && <span className="run-dot" />}
        {blocked && <span className="lock-badge">🔒</span>}
      </button>
      <span className="app-label">{tile.name}</span>
    </div>
  );
}
