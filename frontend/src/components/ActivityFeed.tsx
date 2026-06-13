import type { TilesEvent } from "../types";

const LABEL: Record<string, string> = {
  "tile.activated": "activated",
  "tile.deactivated": "stopped",
  "tile.run": "ran",
  "action.executed": "executed",
  "action.queued": "queued for approval",
  "action.rejected": "rejected",
  "approval.resolved": "approval resolved",
};

function fmtTime(ts: number | null): string {
  if (!ts) return "";
  return new Date(ts * 1000).toLocaleTimeString();
}

export function ActivityFeed({ events }: { events: TilesEvent[] }) {
  return (
    <div className="panel">
      <h2 className="panel-title">Activity</h2>
      {events.length === 0 ? (
        <p className="empty">Live activity appears here.</p>
      ) : (
        <ul className="feed">
          {events.map((e, i) => (
            <li key={i} className="feed-item">
              <span className="feed-time">{fmtTime(e.ts)}</span>
              <span className="feed-tile">{e.tile_id ?? "—"}</span>
              <span className="feed-label">{LABEL[e.type] ?? e.type}</span>
              {typeof e.data.tool === "string" && (
                <span className="pill pill-tool">{e.data.tool}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
