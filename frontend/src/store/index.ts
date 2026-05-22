import { create } from 'zustand'
import type { Conversation, ConversationDetail, Message, Provider } from '../types'

interface AppState {
  // Conversations
  conversations: Conversation[]
  activeConversationId: string | null
  activeConversation: ConversationDetail | null
  setConversations: (convs: Conversation[]) => void
  setActiveConversation: (conv: ConversationDetail | null) => void
  setActiveConversationId: (id: string | null) => void
  addConversation: (conv: Conversation) => void
  updateConversation: (conv: Conversation) => void
  removeConversation: (id: string) => void
  appendMessage: (msg: Message) => void
  updateLastMessage: (content: string) => void

  // Providers
  providers: Record<string, Provider>
  selectedProvider: string
  selectedModel: string
  setProviders: (p: Record<string, Provider>) => void
  setSelectedProvider: (p: string) => void
  setSelectedModel: (m: string) => void

  // UI state
  isStreaming: boolean
  setIsStreaming: (v: boolean) => void
  activeTab: 'chat' | 'dashboard'
  setActiveTab: (t: 'chat' | 'dashboard') => void
  sidebarOpen: boolean
  setSidebarOpen: (v: boolean) => void
}

export const useStore = create<AppState>((set, get) => ({
  conversations: [],
  activeConversationId: null,
  activeConversation: null,

  setConversations: (convs) => set({ conversations: convs }),
  setActiveConversation: (conv) => set({ activeConversation: conv }),
  setActiveConversationId: (id) => set({ activeConversationId: id }),

  addConversation: (conv) =>
    set((s) => ({ conversations: [conv, ...s.conversations] })),

  updateConversation: (conv) =>
    set((s) => ({
      conversations: s.conversations.map((c) => (c.id === conv.id ? conv : c)),
      activeConversation:
        s.activeConversation?.id === conv.id
          ? { ...s.activeConversation, ...conv }
          : s.activeConversation,
    })),

  removeConversation: (id) =>
    set((s) => ({
      conversations: s.conversations.filter((c) => c.id !== id),
      activeConversationId: s.activeConversationId === id ? null : s.activeConversationId,
      activeConversation: s.activeConversation?.id === id ? null : s.activeConversation,
    })),

  appendMessage: (msg) =>
    set((s) => {
      if (!s.activeConversation) return {}
      return {
        activeConversation: {
          ...s.activeConversation,
          messages: [...s.activeConversation.messages, msg],
        },
      }
    }),

  updateLastMessage: (content) =>
    set((s) => {
      if (!s.activeConversation) return {}
      const msgs = [...s.activeConversation.messages]
      if (msgs.length === 0) return {}
      msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], content }
      return { activeConversation: { ...s.activeConversation, messages: msgs } }
    }),

  providers: {},
  selectedProvider: 'groq',
  selectedModel: 'llama-3.1-8b-instant',
  setProviders: (p) => set({ providers: p }),
  setSelectedProvider: (p) => set({ selectedProvider: p }),
  setSelectedModel: (m) => set({ selectedModel: m }),

  isStreaming: false,
  setIsStreaming: (v) => set({ isStreaming: v }),
  activeTab: 'chat',
  setActiveTab: (t) => set({ activeTab: t }),
  sidebarOpen: true,
  setSidebarOpen: (v) => set({ sidebarOpen: v }),
}))
