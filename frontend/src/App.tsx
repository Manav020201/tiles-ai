import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Approval, Provider, Tile, TilesEvent } from "./types";
import { Onboarding } from "./components/Onboarding";
import { TileCard } from "./components/TileCard";
import { Approvals } from "./components/Approvals";
import { ActivityFeed } from "./components/ActivityFeed";
import { TileSettings } from "./components/TileSettings";

export function App() {
  const [providers, setProviders] = useState<Provider[] | null>(null);
  const [tiles, setTiles] = useState<Tile[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [events, setEvents] = useState<TilesEvent[]>([]);
  const [settingsFor, setSettingsFor] = useState<string | null>(null);

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
  const settingsTile = tiles.find((t) => t.id === settingsFor) ?? null;

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
                  <TileCard
                    key={tile.id}
                    tile={tile}
                    onChanged={refresh}
                    onOpenSettings={() => setSettingsFor(tile.id)}
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

      {settingsTile && (
        <TileSettings
          tile={settingsTile}
          providers={providers}
          onClose={() => setSettingsFor(null)}
          onChanged={refresh}
        />
      )}
    </div>
  );
}

interface TileGroup {
  heading: string;
  hint: string | null;
  items: Tile[];
}

// Instant tiles (no connector) lead — they need zero setup. App tiles follow,
// grouped by connector to make "one connector, many tiles" visible.
function groupTiles(tiles: Tile[]): TileGroup[] {
  const instant = tiles.filter((t) => t.connector === null);
  const groups: TileGroup[] = [];
  if (instant.length) {
    groups.push({ heading: "Instant", hint: "no setup", items: instant });
  }
  const byConnector = new Map<string, Tile[]>();
  for (const t of tiles) {
    if (t.connector === null) continue;
    const list = byConnector.get(t.connector) ?? [];
    list.push(t);
    byConnector.set(t.connector, list);
  }
  for (const [connector, items] of byConnector) {
    groups.push({ heading: connector, hint: null, items });
  }
  return groups;
}
