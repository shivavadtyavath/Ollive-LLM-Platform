import { useEffect, useRef, useState } from 'react'
import { Send, StopCircle, Play, Zap, MessageSquare } from 'lucide-react'
import clsx from 'clsx'
import { useStore } from '../../store'
import { conversationsApi, streamMessage } from '../../api/client'
import { MessageBubble } from './MessageBubble'
import { ProviderSelector } from './ProviderSelector'
import type { Message } from '../../types'

export function ChatWindow() {
  const {
    activeConversation, activeConversationId,
    appendMessage, updateLastMessage, updateConversation,
    isStreaming, setIsStreaming,
    selectedProvider, selectedModel,
    addConversation, setActiveConversationId, setActiveConversation,
  } = useStore()

  const [input, setInput] = useState('')
  const [useStream, setUseStream] = useState(true)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [activeConversation?.messages])

  async function ensureConversation(): Promise<string> {
    if (activeConversationId) return activeConversationId
    const res = await conversationsApi.create({
      provider: selectedProvider,
      model: selectedModel,
    })
    const conv = res.data
    addConversation(conv)
    setActiveConversationId(conv.id)
    setActiveConversation({ ...conv, messages: [] })
    return conv.id
  }

  async function handleSend() {
    const content = input.trim()
    if (!content || isStreaming) return

    setInput('')
    setIsStreaming(true)

    const convId = await ensureConversation()

    // Optimistically add user message
    const userMsg: Message = {
      id: crypto.randomUUID(),
      conversation_id: convId,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    }
    appendMessage(userMsg)

    if (useStream) {
      // Add placeholder assistant message
      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        conversation_id: convId,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
      }
      appendMessage(assistantMsg)

      try {
        let fullText = ''
        for await (const chunk of streamMessage(convId, content, selectedProvider, selectedModel)) {
          fullText += chunk
          updateLastMessage(fullText)
        }
      } catch (e) {
        updateLastMessage('Sorry, something went wrong. Please try again.')
      }
    } else {
      try {
        const res = await conversationsApi.sendMessage(convId, content, selectedProvider, selectedModel)
        appendMessage(res.data)
      } catch (e) {
        appendMessage({
          id: crypto.randomUUID(),
          conversation_id: convId,
          role: 'assistant',
          content: 'Sorry, something went wrong. Please try again.',
          created_at: new Date().toISOString(),
        })
      }
    }

    setIsStreaming(false)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const isCancelled = activeConversation?.status === 'cancelled'
  const messages = activeConversation?.messages || []

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-gray-800 bg-gray-900/50">
        <div className="flex items-center gap-3">
          <MessageSquare size={16} className="text-brand-400" />
          <div>
            <h2 className="text-sm font-semibold text-white truncate max-w-xs">
              {activeConversation?.title || 'New conversation'}
            </h2>
            {activeConversation && (
              <p className="text-[10px] text-gray-500">
                {messages.length} messages · {activeConversation.provider} / {activeConversation.model}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Stream toggle */}
          <button
            onClick={() => setUseStream(!useStream)}
            className={clsx(
              'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors border',
              useStream
                ? 'bg-brand-900/50 border-brand-700 text-brand-300'
                : 'bg-gray-800 border-gray-700 text-gray-400'
            )}
            title="Toggle streaming"
          >
            <Zap size={11} />
            {useStream ? 'Streaming' : 'Batch'}
          </button>

          <ProviderSelector />
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-16 h-16 rounded-2xl bg-brand-600/20 flex items-center justify-center mb-4">
              <Zap size={28} className="text-brand-400" />
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">Start a conversation</h3>
            <p className="text-sm text-gray-500 max-w-sm">
              Ask anything. Your conversation is logged with full inference metadata.
            </p>
            <div className="mt-6 grid grid-cols-2 gap-2 max-w-md">
              {[
                'Explain async/await in Python',
                'Write a binary search in TypeScript',
                'What is RAG in LLMs?',
                'Design a REST API for a blog',
              ].map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => setInput(prompt)}
                  className="text-left px-3 py-2 rounded-xl bg-gray-800 hover:bg-gray-700 text-xs text-gray-300 transition-colors border border-gray-700"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            isStreaming={isStreaming && i === messages.length - 1 && msg.role === 'assistant'}
          />
        ))}

        {isCancelled && (
          <div className="flex items-center justify-center">
            <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-red-900/30 border border-red-800 text-red-400 text-xs">
              <StopCircle size={12} />
              Conversation cancelled — resume to continue
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-6 py-4 border-t border-gray-800 bg-gray-900/50">
        {isCancelled ? (
          <div className="flex items-center justify-center gap-3">
            <p className="text-sm text-gray-500">This conversation is cancelled.</p>
            <button
              onClick={async () => {
                if (!activeConversationId) return
                const res = await conversationsApi.resume(activeConversationId)
                updateConversation(res.data)
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-green-700 hover:bg-green-600 text-white text-xs font-medium transition-colors"
            >
              <Play size={12} />
              Resume
            </button>
          </div>
        ) : (
          <div className="flex items-end gap-3">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Message… (Enter to send, Shift+Enter for newline)"
              rows={1}
              disabled={isStreaming}
              className="flex-1 resize-none bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-brand-500 transition-colors disabled:opacity-50 max-h-40 overflow-y-auto"
              style={{ minHeight: '48px' }}
              onInput={(e) => {
                const t = e.currentTarget
                t.style.height = 'auto'
                t.style.height = Math.min(t.scrollHeight, 160) + 'px'
              }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isStreaming}
              className="p-3 rounded-xl bg-brand-600 hover:bg-brand-700 text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
            >
              <Send size={16} />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
