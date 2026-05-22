import { useEffect } from 'react'
import { ChevronDown, Zap, Server, Globe, Lock } from 'lucide-react'
import { useStore } from '../../store'
import { providersApi } from '../../api/client'

const PROVIDER_ICONS: Record<string, React.ReactNode> = {
  groq: <Zap size={12} className="text-yellow-400" />,
  ollama: <Server size={12} className="text-green-400" />,
  openrouter: <Globe size={12} className="text-blue-400" />,
  openai: <Lock size={12} className="text-gray-400" />,
}

export function ProviderSelector() {
  const {
    providers, setProviders,
    selectedProvider, selectedModel,
    setSelectedProvider, setSelectedModel,
  } = useStore()

  useEffect(() => {
    // Load providers catalog
    providersApi.list().then((res) => setProviders(res.data)).catch(console.error)

    // Sync default provider/model from backend
    providersApi.getDefault().then((res) => {
      setSelectedProvider(res.data.provider)
      setSelectedModel(res.data.model)
    }).catch(console.error)
  }, [])

  const currentProvider = providers[selectedProvider]
  const currentModel = currentProvider?.models.find((m) => m.id === selectedModel)

  return (
    <div className="flex items-center gap-2">
      {/* Provider dropdown */}
      <div className="relative group">
        <button className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-xs text-gray-300 transition-colors border border-gray-700">
          {PROVIDER_ICONS[selectedProvider]}
          <span className="font-medium">{currentProvider?.name || selectedProvider}</span>
          <ChevronDown size={10} className="text-gray-500" />
        </button>
        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block z-50 w-56 bg-gray-800 border border-gray-700 rounded-xl shadow-xl overflow-hidden">
          {Object.entries(providers).map(([key, p]: [string, any]) => (
            <button
              key={key}
              onClick={() => {
                setSelectedProvider(key)
                setSelectedModel(p.models[0]?.id || '')
              }}
              className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-700 text-left transition-colors"
            >
              {PROVIDER_ICONS[key]}
              <div>
                <p className="text-xs font-medium text-gray-200">{p.name}</p>
                <p className="text-[10px] text-gray-500">{p.description}</p>
              </div>
              {p.free && (
                <span className="ml-auto text-[9px] px-1.5 py-0.5 rounded-full bg-green-900/50 text-green-400 font-medium">
                  FREE
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Model dropdown */}
      <div className="relative group">
        <button className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-xs text-gray-300 transition-colors border border-gray-700">
          <span>{currentModel?.name || selectedModel}</span>
          <ChevronDown size={10} className="text-gray-500" />
        </button>
        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block z-50 w-64 bg-gray-800 border border-gray-700 rounded-xl shadow-xl overflow-hidden">
          {currentProvider?.models.map((m) => (
            <button
              key={m.id}
              onClick={() => setSelectedModel(m.id)}
              className={`w-full flex items-center justify-between px-3 py-2 hover:bg-gray-700 text-left transition-colors ${
                m.id === selectedModel ? 'bg-gray-700/50' : ''
              }`}
            >
              <span className="text-xs text-gray-200">{m.name}</span>
              <span className="text-[10px] text-gray-500">{(m.context / 1000).toFixed(0)}k ctx</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
