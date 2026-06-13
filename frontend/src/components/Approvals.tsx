import { useState } from "react";
import { api } from "../api";
import type { Approval } from "../types";

export function Approvals({
  approvals,
  onChanged,
}: {
  approvals: Approval[];
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);

  async function resolve(id: string, approved: boolean) {
    setBusy(id);
    try {
      await api.resolveApproval(id, approved);
      onChanged();
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="panel">
      <h2 className="panel-title">
        Approvals {approvals.length > 0 && <span className="count">{approvals.length}</span>}
      </h2>
      {approvals.length === 0 ? (
        <p className="empty">No actions waiting. Draft tiles queue here.</p>
      ) : (
        <ul className="approval-list">
          {approvals.map((a) => (
            <li key={a.id} className="approval">
              <div className="approval-head">
                <span className="approval-tile">{a.tile_id}</span>
                <span className="pill pill-tool">{a.tool}</span>
              </div>
              <div className="approval-summary">{a.summary || JSON.stringify(a.args)}</div>
              <div className="approval-actions">
                <button
                  className="btn btn-approve"
                  disabled={busy === a.id}
                  onClick={() => resolve(a.id, true)}
                >
                  Approve
                </button>
                <button
                  className="btn btn-reject"
                  disabled={busy === a.id}
                  onClick={() => resolve(a.id, false)}
                >
                  Reject
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
