import type { LoadError } from "../types";

// Surfaces tiles/connectors that failed to load, with the exact reason — so a
// beginner who edits a manifest or handler and breaks it learns why, on the board.
export function Issues({ errors }: { errors: LoadError[] }) {
  if (errors.length === 0) return null;
  return (
    <div className="panel panel-issues">
      <h2 className="panel-title">
        Issues <span className="count">{errors.length}</span>
      </h2>
      <ul className="issue-list">
        {errors.map((e, i) => (
          <li key={i} className="issue">
            <div className="issue-head">
              <span className="pill pill-warn">{e.kind}</span>
              <span className="issue-source">{e.source}</span>
            </div>
            {e.errors.map((msg, j) => (
              <div key={j} className="issue-msg">
                {msg}
              </div>
            ))}
          </li>
        ))}
      </ul>
    </div>
  );
}
