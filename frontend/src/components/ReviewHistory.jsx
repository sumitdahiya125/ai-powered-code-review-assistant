export default function ReviewHistory({ items, onSelect, activeId }) {
  if (!items || items.length === 0) {
    return (
      <div className="history">
        <h3>Recent reviews</h3>
        <div className="empty small">No history yet.</div>
      </div>
    );
  }

  return (
    <div className="history">
      <h3>Recent reviews</h3>
      <ul>
        {items.map((r) => {
          const total =
            (r.summary?.critical ?? 0) +
            (r.summary?.error ?? 0) +
            (r.summary?.warning ?? 0) +
            (r.summary?.info ?? 0);
          const isActive = r.id === activeId;
          return (
            <li
              key={r.id}
              className={`history-item ${isActive ? 'active' : ''}`}
              onClick={() => onSelect(r.id)}
            >
              <div className="row">
                <span className="lang">{r.language}</span>
                <span className="when">
                  {new Date(r.created_at).toLocaleTimeString()}
                </span>
              </div>
              <div className="row sub">
                <span>{total} finding{total === 1 ? '' : 's'}</span>
                {r.cached && <span className="badge cached">cached</span>}
                <span className="latency">{r.latency_ms} ms</span>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
