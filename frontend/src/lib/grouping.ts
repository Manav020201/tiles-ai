import type { Tile } from "../types";

export interface TileGroup {
  heading: string;
  hint: string | null;
  items: Tile[];
}

// Instant tiles (no connector) lead — they need zero setup. App tiles follow,
// grouped by connector to make "one connector, many tiles" visible.
export function groupTiles(tiles: Tile[]): TileGroup[] {
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
