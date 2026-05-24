const SEVERITY_CLASS = {
  critical: 'sev-critical',
  error: 'sev-error',
  warning: 'sev-warning',
  info: 'sev-info',
};

export default function ReviewResults({ review }) {
  if (!review) {
    return <div className="empty">Submit code to see findings here.</div>;
  }

  const { summary, findings, latency_ms, cached, language } = review;
  const total = findings.length;

  return (
    <div className="results">
      <div className="results-header">
        <h2>Findings ({total})</h2>
        <div className="result-meta">
          <span>{language}</span>
          <span>{latency_ms} ms</span>
          {cached && <span className="badge cached">cache hit</span>}
        </div>
      </div>

      <div className="summary-row">
        {['critical', 'error', 'warning', 'info'].map((sev) => (
          <div key={sev} className={`summary-chip ${SEVERITY_CLASS[sev]}`}>
            <strong>{summary[sev] ?? 0}</strong>
            <span>{sev}</span>
          </div>
        ))}
      </div>

      {total === 0 ? (
        <div className="empty success">No issues found. Looks clean.</div>
      ) : (
        <ul className="findings">
          {findings.map((f, i) => (
            <li key={`${f.rule_id}-${f.line ?? 'na'}-${i}`} className={`finding ${SEVERITY_CLASS[f.severity]}`}>
              <div className="finding-head">
                <span className="rule">{f.rule_id}</span>
                <span className={`pill ${SEVERITY_CLASS[f.severity]}`}>{f.severity}</span>
                <span className="category">{f.category}</span>
                {f.line != null && <span className="line">line {f.line}</span>}
                {f.confidence < 1 && (
                  <span className="confidence">conf {Math.round(f.confidence * 100)}%</span>
                )}
              </div>
              <div className="finding-msg">{f.message}</div>
              {f.suggestion && <div className="finding-suggestion">→ {f.suggestion}</div>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
