import { useCallback, useEffect, useState } from 'react';
import CodeEditor from './components/CodeEditor.jsx';
import ReviewResults from './components/ReviewResults.jsx';
import ReviewHistory from './components/ReviewHistory.jsx';
import StatsPanel from './components/StatsPanel.jsx';
import { api } from './api.js';

const SAMPLE_CODE = `def login(user, pw):
    query = "SELECT * FROM users WHERE name=" + user
    return db.execute(query)

API_KEY = "sk-abcdef1234567890abcdef"

def process(items=[]):
    try:
        return [eval(x) for x in items]
    except:
        return None
`;

export default function App() {
  const [language, setLanguage] = useState('python');
  const [code, setCode] = useState(SAMPLE_CODE);
  const [review, setReview] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);
  const [stats, setStats] = useState(null);

  const refreshSidebar = useCallback(async () => {
    try {
      const [list, summary] = await Promise.all([api.listReviews(15), api.stats()]);
      setHistory(list);
      setStats(summary);
    } catch (e) {
      // Sidebar is best-effort.
      console.warn('sidebar refresh failed', e);
    }
  }, []);

  useEffect(() => {
    refreshSidebar();
  }, [refreshSidebar]);

  const onSubmit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.submitReview(language, code);
      setReview(result);
      refreshSidebar();
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const onPick = async (id) => {
    setError(null);
    try {
      const result = await api.getReview(id);
      setReview(result);
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>AI Code Review Assistant</h1>
        <span className="tag">FastAPI · CodeBERT · Postgres · Redis</span>
      </header>

      <main className="layout">
        <section className="editor-pane">
          <div className="toolbar">
            <label>
              Language:&nbsp;
              <select value={language} onChange={(e) => setLanguage(e.target.value)}>
                <option value="python">python</option>
                <option value="javascript">javascript</option>
                <option value="typescript">typescript</option>
                <option value="go">go</option>
                <option value="java">java</option>
              </select>
            </label>
            <button onClick={onSubmit} disabled={submitting || !code.trim()}>
              {submitting ? 'Reviewing…' : 'Run review'}
            </button>
          </div>
          <CodeEditor language={language} value={code} onChange={setCode} />
        </section>

        <section className="results-pane">
          {error && <div className="error">{error}</div>}
          <ReviewResults review={review} />
        </section>

        <aside className="sidebar">
          <StatsPanel stats={stats} />
          <ReviewHistory items={history} onSelect={onPick} activeId={review?.id} />
        </aside>
      </main>
    </div>
  );
}
