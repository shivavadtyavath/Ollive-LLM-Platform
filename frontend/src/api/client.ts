import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 60_000,
})

// ── Conversations ─────────────────────────────────────────────────────────────

export const conversationsApi = {
  list: (status?: string) =>
    api.get('/conversations', { params: status ? { status } : {} }),

  get: (id: string) =>
    api.get(`/conversations/${id}`),

  create: (data: { title?: string; provider?: string; model?: string }) =>
    api.post('/conversations', data),

  cancel: (id: string) =>
    api.post(`/conversations/${id}/cancel`),

  resume: (id: string) =>
    api.post(`/conversations/${id}/resume`),

  delete: (id: string) =>
    api.delete(`/conversations/${id}`),

  sendMessage: (id: string, content: string, provider?: string, model?: string) =>
    api.post(`/conversations/${id}/messages`, { content, provider, model }),
}

// ── Providers ─────────────────────────────────────────────────────────────────

export const providersApi = {
  list: () => api.get('/providers'),
  getDefault: () => api.get('/providers/default'),
}

// ── Metrics ───────────────────────────────────────────────────────────────────

export const metricsApi = {
  summary: (hours = 24) => api.get('/metrics/summary', { params: { hours } }),
  latencyOverTime: (hours = 24) => api.get('/metrics/latency-over-time', { params: { hours } }),
  providerStats: (hours = 24) => api.get('/metrics/provider-stats', { params: { hours } }),
  recentLogs: (limit = 50, status?: string, provider?: string) =>
    api.get('/metrics/recent-logs', { params: { limit, status, provider } }),
}

// ── Streaming ─────────────────────────────────────────────────────────────────

export async function* streamMessage(
  conversationId: string,
  content: string,
  provider?: string,
  model?: string,
): AsyncGenerator<string> {
  const url = `${BASE_URL}/conversations/${conversationId}/messages/stream`
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, provider, model, stream: true }),
  })

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    const text = decoder.decode(value, { stream: true })
    const lines = text.split('\n')

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6)
        if (data === '[DONE]') return
        if (data) yield data
      }
    }
  }
}
