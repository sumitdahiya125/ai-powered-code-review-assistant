export default function StatsPanel({ stats }) {
  if (!stats) {
    return (
      <div className="stats">
        <h3>Stats</h3>
        <div className="empty small">Loading…</div>
      </div>
    );
  }

  const sevOrder = ['critical', 'error', 'warning', 'info'];

  return (
    <div className="stats">
      <h3>Stats</h3>
      <div className="kv">
        <span>Total reviews</span>
        <strong>{stats.total_reviews}</strong>
      </div>
      <div className="kv">
        <span>Avg latency</span>
        <strong>{Math.round(stats.avg_latency_ms)} ms</strong>
      </div>
      <div className="kv">
        <span>Cache hit rate</span>
        <strong>{Math.round((stats.cache_hit_rate ?? 0) * 100)}%</strong>
      </div>

      <div className="stat-section">
        <div className="stat-label">By severity</div>
        {sevOrder.map((sev) => (
          <div key={sev} className={`stat-bar sev-${sev}`}>
            <span>{sev}</span>
            <strong>{stats.by_severity?.[sev] ?? 0}</strong>
          </div>
        ))}
      </div>

      <div className="stat-section">
        <div className="stat-label">By category</div>
        {Object.entries(stats.by_category || {}).map(([cat, count]) => (
          <div key={cat} className="stat-bar">
            <span>{cat}</span>
            <strong>{count}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}
