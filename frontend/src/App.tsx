import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Approval, Provider, Tile, TilesEvent } from "./types";
import { Onboarding } from "./components/Onboarding";
import { TileIcon } from "./components/TileIcon";
import { TileSheet } from "./components/TileSheet";
import { Approvals } from "./components/Approvals";
import { ActivityFeed } from "./components/ActivityFeed";
import { groupTiles } from "./lib/grouping";

export function App() {
  const [providers, setProviders] = useState<Provider[] | null>(null);
  const [tiles, setTiles] = useState<Tile[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [events, setEvents] = useState<TilesEvent[]>([]);
  const [openTileId, setOpenTileId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [t, a, p] = await Promise.all([
      api.listTiles(),
      api.listApprovals(),
      api.listProviders(),
    ]);
    setTiles(t);
    setApprovals(a);
    setProviders(p);
  }, []);

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
          Brain:{" "}
          {defaultProvider ? (
            <span className="pill pill-brain">
              {defaultProvider.model}
            </span>
          ) : (
            <span className="pill pill-warn">no default</span>
          )}
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
        </section>

        <aside className="sidebar">
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
        />
      )}
    </div>
  );
}
