const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function handle(response) {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status}: ${text || response.statusText}`);
  }
  return response.json();
}

export const api = {
  submitReview(language, code) {
    return fetch(`${BASE}/api/reviews`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ language, code }),
    }).then(handle);
  },

  listReviews(limit = 20) {
    return fetch(`${BASE}/api/reviews?limit=${limit}`).then(handle);
  },

  getReview(id) {
    return fetch(`${BASE}/api/reviews/${id}`).then(handle);
  },

  stats() {
    return fetch(`${BASE}/api/reviews/stats`).then(handle);
  },
};
