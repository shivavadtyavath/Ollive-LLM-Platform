export type ConversationStatus = 'active' | 'cancelled' | 'archived'
export type MessageRole = 'user' | 'assistant' | 'system'

export interface Message {
  id: string
  conversation_id: string
  role: MessageRole
  content: string
  token_count?: number
  created_at: string
}

export interface Conversation {
  id: string
  title: string
  status: ConversationStatus
  provider: string
  model: string
  created_at: string
  updated_at: string
  message_count: number
}

export interface ConversationDetail extends Conversation {
  messages: Message[]
}

export interface Provider {
  name: string
  description: string
  free: boolean
  models: Model[]
}

export interface Model {
  id: string
  name: string
  context: number
}

export interface MetricsSummary {
  total_requests: number
  success_count: number
  error_count: number
  avg_latency_ms: number | null
  p95_latency_ms: number | null
  total_tokens: number | null
  requests_per_provider: Record<string, number>
  requests_per_model: Record<string, number>
  error_rate: number
}

export interface LatencyBucket {
  timestamp: string
  avg_latency_ms: number
  request_count: number
}

export interface ProviderStats {
  provider: string
  model: string
  total_requests: number
  success_rate: number
  avg_latency_ms: number
  total_tokens: number
}

export interface InferenceLog {
  id: string
  conversation_id: string
  provider: string
  model: string
  latency_ms: number | null
  status: string
  total_tokens: number | null
  is_streaming: boolean
  created_at: string
}
