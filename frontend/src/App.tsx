import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Approval, LoadError, Provider, Tile, TilesEvent } from "./types";
import { Onboarding } from "./components/Onboarding";
import { TileIcon } from "./components/TileIcon";
import { TileSheet } from "./components/TileSheet";
import { Approvals } from "./components/Approvals";
import { ActivityFeed } from "./components/ActivityFeed";
import { NewTileForm } from "./components/NewTileForm";
import { AddConnectorForm } from "./components/AddConnectorForm";
import { EditTileForm } from "./components/EditTileForm";
import { Settings } from "./components/Settings";
import { Issues } from "./components/Issues";
import { groupTiles } from "./lib/grouping";

export function App() {
  const [providers, setProviders] = useState<Provider[] | null>(null);
  const [tiles, setTiles] = useState<Tile[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [events, setEvents] = useState<TilesEvent[]>([]);
  const [errors, setErrors] = useState<LoadError[]>([]);
  const [openTileId, setOpenTileId] = useState<string | null>(null);
  const [editingTileId, setEditingTileId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [addingApp, setAddingApp] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  const refresh = useCallback(async () => {
    const [t, a, p, e] = await Promise.all([
      api.listTiles(),
      api.listApprovals(),
      api.listProviders(),
      api.listErrors(),
    ]);
    setTiles(t);
    setApprovals(a);
    setProviders(p);
    setErrors(e);
  }, []);

  const rescan = useCallback(async () => {
    await api.reload();
    refresh();
  }, [refresh]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Live event stream: append to the feed and refresh the board state.
  const refreshRef = useRef(refresh);
  refreshRef.current = refresh;
  useEffect(() => {
    const source = new EventSource("/api/events");
    const onEvent = (e: MessageEvent) => {
      try {
        const parsed: TilesEvent = JSON.parse(e.data);
        setEvents((prev) => [parsed, ...prev].slice(0, 100));
        refreshRef.current();
      } catch {
        /* keepalive / non-JSON frame */
      }
    };
    for (const type of [
      "tile.activated",
      "tile.deactivated",
      "tile.run",
      "action.executed",
      "action.queued",
      "action.rejected",
      "approval.resolved",
    ]) {
      source.addEventListener(type, onEvent);
    }
    source.onerror = () => {
      /* browser auto-reconnects */
    };
    return () => source.close();
  }, []);

  if (providers === null) {
    return <div className="loading">Loading…</div>;
  }

  // First launch: no brain connected yet -> onboarding.
  if (providers.length === 0) {
    return <Onboarding onDone={refresh} />;
  }

  const defaultProvider = providers.find((p) => p.is_default);
  const openTile = tiles.find((t) => t.id === openTileId) ?? null;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">▦</span> Tiles AI
        </div>
        <div className="brain-summary">
          <button className="icon-btn" onClick={rescan} title="Re-scan tiles & connectors from disk">
            ⟳
          </button>
          <button
            className="brain-chip"
            onClick={() => setShowSettings(true)}
            title="Manage brains (models)"
          >
            🧠{" "}
            {defaultProvider ? (
              defaultProvider.model
            ) : (
              <span className="pill pill-warn">connect a brain</span>
            )}
          </button>
        </div>
      </header>

      <main className="layout">
        <section className="board-area">
          {groupTiles(tiles).map(({ heading, hint, items }) => (
            <div className="board-group" key={heading}>
              <h2 className="group-title">
                {heading}
                {hint && <span className="group-hint">{hint}</span>}
              </h2>
              <div className="board">
                {items.map((tile) => (
                  <TileIcon
                    key={tile.id}
                    tile={tile}
                    onOpen={() => setOpenTileId(tile.id)}
                  />
                ))}
              </div>
            </div>
          ))}

          <div className="board-group">
            <h2 className="group-title">Create</h2>
            <div className="board">
              <div className="app-cell">
                <button
                  className="app-icon add-icon"
                  onClick={() => setCreating(true)}
                  title="Create a new tile"
                >
                  ＋
                </button>
                <span className="app-label">New tile</span>
              </div>
              <div className="app-cell">
                <button
                  className="app-icon add-icon"
                  onClick={() => setAddingApp(true)}
                  title="Connect a new application"
                >
                  🔌
                </button>
                <span className="app-label">New app</span>
              </div>
            </div>
          </div>
        </section>

        <aside className="sidebar">
          <Issues errors={errors} />
          <Approvals approvals={approvals} onChanged={refresh} />
          <ActivityFeed events={events} />
        </aside>
      </main>

      {openTile && (
        <TileSheet
          tile={openTile}
          providers={providers}
          onClose={() => setOpenTileId(null)}
          onChanged={refresh}
          onEdit={() => {
            setEditingTileId(openTile.id);
            setOpenTileId(null);
          }}
        />
      )}

      {editingTileId && (
        <EditTileForm
          tileId={editingTileId}
          onClose={() => setEditingTileId(null)}
          onSaved={refresh}
        />
      )}

      {creating && <NewTileForm onClose={() => setCreating(false)} onCreated={refresh} />}

      {addingApp && (
        <AddConnectorForm onClose={() => setAddingApp(false)} onCreated={refresh} />
      )}

      {showSettings && (
        <Settings
          providers={providers}
          onChanged={refresh}
          onClose={() => setShowSettings(false)}
        />
      )}
    </div>
  );
}
