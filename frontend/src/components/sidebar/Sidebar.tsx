import { useEffect, useState } from 'react'
import { formatDistanceToNow } from 'date-fns'
import {
  MessageSquare, Plus, LayoutDashboard, Trash2,
  StopCircle, Play, ChevronLeft, ChevronRight, Zap
} from 'lucide-react'
import clsx from 'clsx'
import { useStore } from '../../store'
import { conversationsApi } from '../../api/client'
import type { Conversation } from '../../types'

export function Sidebar() {
  const {
    conversations, setConversations, activeConversationId,
    setActiveConversationId, setActiveConversation,
    addConversation, updateConversation, removeConversation,
    activeTab, setActiveTab, sidebarOpen, setSidebarOpen,
    selectedProvider, selectedModel,
  } = useStore()

  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadConversations()
  }, [])

  async function loadConversations() {
    try {
      const res = await conversationsApi.list()
      setConversations(res.data)
    } catch (e) {
      console.error(e)
    }
  }

  async function newConversation() {
    setLoading(true)
    try {
      const res = await conversationsApi.create({
        provider: selectedProvider,
        model: selectedModel || 'llama-3.1-8b-instant',
      })
      const conv: Conversation = res.data
      addConversation(conv)
      setActiveConversationId(conv.id)
      setActiveConversation({ ...conv, messages: [] })
      setActiveTab('chat')
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  async function handleCancel(e: React.MouseEvent, id: string) {
    e.stopPropagation()
    try {
      const res = await conversationsApi.cancel(id)
      updateConversation(res.data)
    } catch (e) { console.error(e) }
  }

  async function handleResume(e: React.MouseEvent, id: string) {
    e.stopPropagation()
    try {
      const res = await conversationsApi.resume(id)
      updateConversation(res.data)
    } catch (e) { console.error(e) }
  }

  async function handleDelete(e: React.MouseEvent, id: string) {
    e.stopPropagation()
    if (!confirm('Delete this conversation?')) return
    try {
      await conversationsApi.delete(id)
      removeConversation(id)
    } catch (e) { console.error(e) }
  }

  async function selectConversation(conv: Conversation) {
    setActiveConversationId(conv.id)
    setActiveTab('chat')
    try {
      const res = await conversationsApi.get(conv.id)
      setActiveConversation(res.data)
    } catch (e) { console.error(e) }
  }

  return (
    <aside
      className={clsx(
        'flex flex-col h-full bg-gray-900 border-r border-gray-800 transition-all duration-300',
        sidebarOpen ? 'w-72' : 'w-14'
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-800">
        {sidebarOpen && (
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-brand-600 flex items-center justify-center">
              <Zap size={14} className="text-white" />
            </div>
            <span className="font-semibold text-white text-sm">Ollive</span>
          </div>
        )}
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="p-1.5 rounded-lg hover:bg-gray-800 text-gray-400 hover:text-white transition-colors ml-auto"
        >
          {sidebarOpen ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
        </button>
      </div>

      {/* Nav */}
      <div className="p-2 border-b border-gray-800 space-y-1">
        <button
          onClick={() => setActiveTab('chat')}
          className={clsx(
            'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
            activeTab === 'chat'
              ? 'bg-brand-600 text-white'
              : 'text-gray-400 hover:text-white hover:bg-gray-800'
          )}
        >
          <MessageSquare size={16} />
          {sidebarOpen && 'Chat'}
        </button>
        <button
          onClick={() => setActiveTab('dashboard')}
          className={clsx(
            'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
            activeTab === 'dashboard'
              ? 'bg-brand-600 text-white'
              : 'text-gray-400 hover:text-white hover:bg-gray-800'
          )}
        >
          <LayoutDashboard size={16} />
          {sidebarOpen && 'Dashboard'}
        </button>
      </div>

      {/* New chat button */}
      {sidebarOpen && (
        <div className="p-2">
          <button
            onClick={newConversation}
            disabled={loading}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium transition-colors disabled:opacity-50"
          >
            <Plus size={16} />
            New conversation
          </button>
        </div>
      )}

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {conversations.map((conv) => (
          <div
            key={conv.id}
            onClick={() => selectConversation(conv)}
            className={clsx(
              'group relative flex items-start gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-colors',
              activeConversationId === conv.id
                ? 'bg-gray-800 text-white'
                : 'text-gray-400 hover:bg-gray-800/60 hover:text-gray-200'
            )}
          >
            <MessageSquare size={14} className="mt-0.5 shrink-0" />
            {sidebarOpen && (
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium truncate">{conv.title}</p>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className={clsx(
                    'text-[10px] px-1.5 py-0.5 rounded-full font-medium',
                    conv.status === 'active' ? 'bg-green-900/50 text-green-400' :
                    conv.status === 'cancelled' ? 'bg-red-900/50 text-red-400' :
                    'bg-gray-700 text-gray-400'
                  )}>
                    {conv.status}
                  </span>
                  <span className="text-[10px] text-gray-600">
                    {formatDistanceToNow(new Date(conv.updated_at), { addSuffix: true })}
                  </span>
                </div>
              </div>
            )}

            {/* Action buttons */}
            {sidebarOpen && (
              <div className="hidden group-hover:flex items-center gap-1 absolute right-2 top-2">
                {conv.status === 'active' ? (
                  <button
                    onClick={(e) => handleCancel(e, conv.id)}
                    className="p-1 rounded hover:bg-red-900/50 text-gray-500 hover:text-red-400 transition-colors"
                    title="Cancel"
                  >
                    <StopCircle size={12} />
                  </button>
                ) : (
                  <button
                    onClick={(e) => handleResume(e, conv.id)}
                    className="p-1 rounded hover:bg-green-900/50 text-gray-500 hover:text-green-400 transition-colors"
                    title="Resume"
                  >
                    <Play size={12} />
                  </button>
                )}
                <button
                  onClick={(e) => handleDelete(e, conv.id)}
                  className="p-1 rounded hover:bg-red-900/50 text-gray-500 hover:text-red-400 transition-colors"
                  title="Delete"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            )}
          </div>
        ))}

        {conversations.length === 0 && sidebarOpen && (
          <p className="text-xs text-gray-600 text-center py-8">
            No conversations yet.<br />Start a new one above.
          </p>
        )}
      </div>
    </aside>
  )
}
