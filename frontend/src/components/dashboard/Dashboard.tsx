import { useEffect, useState } from 'react'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend
} from 'recharts'
import { Activity, Zap, AlertTriangle, Cpu, Clock, TrendingUp, RefreshCw } from 'lucide-react'
import { metricsApi } from '../../api/client'
import type { MetricsSummary, LatencyBucket, ProviderStats, InferenceLog } from '../../types'
import { formatDistanceToNow } from 'date-fns'

const COLORS = ['#6366f1', '#22d3ee', '#f59e0b', '#10b981', '#f43f5e']

function StatCard({
  icon, label, value, sub, color = 'brand'
}: {
  icon: React.ReactNode
  label: string
  value: string | number
  sub?: string
  color?: string
}) {
  const colorMap: Record<string, string> = {
    brand: 'bg-brand-600/20 text-brand-400',
    green: 'bg-green-600/20 text-green-400',
    red: 'bg-red-600/20 text-red-400',
    yellow: 'bg-yellow-600/20 text-yellow-400',
    cyan: 'bg-cyan-600/20 text-cyan-400',
  }
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
      <div className="flex items-start justify-between mb-3">
        <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${colorMap[color]}`}>
          {icon}
        </div>
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
      <p className="text-xs text-gray-400 mt-1">{label}</p>
      {sub && <p className="text-[10px] text-gray-600 mt-0.5">{sub}</p>}
    </div>
  )
}

export function Dashboard() {
  const [summary, setSummary] = useState<MetricsSummary | null>(null)
  const [latency, setLatency] = useState<LatencyBucket[]>([])
  const [providerStats, setProviderStats] = useState<ProviderStats[]>([])
  const [recentLogs, setRecentLogs] = useState<InferenceLog[]>([])
  const [hours, setHours] = useState(24)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    load()
    const interval = setInterval(load, 30_000)
    return () => clearInterval(interval)
  }, [hours])

  async function load() {
    setLoading(true)
    try {
      const [s, l, p, r] = await Promise.all([
        metricsApi.summary(hours),
        metricsApi.latencyOverTime(hours),
        metricsApi.providerStats(hours),
        metricsApi.recentLogs(20),
      ])
      setSummary(s.data)
      setLatency(l.data)
      setProviderStats(p.data)
      setRecentLogs(r.data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const providerPieData = summary
    ? Object.entries(summary.requests_per_provider).map(([name, value]) => ({ name, value }))
    : []

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Observability Dashboard</h1>
          <p className="text-xs text-gray-500 mt-0.5">Real-time inference metrics</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={hours}
            onChange={(e) => setHours(Number(e.target.value))}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-xs text-gray-300 focus:outline-none"
          >
            <option value={1}>Last 1h</option>
            <option value={6}>Last 6h</option>
            <option value={24}>Last 24h</option>
            <option value={168}>Last 7d</option>
          </select>
          <button
            onClick={load}
            disabled={loading}
            className="p-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white transition-colors disabled:opacity-50"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<Activity size={16} />}
          label="Total Requests"
          value={summary?.total_requests ?? '—'}
          sub={`Last ${hours}h`}
          color="brand"
        />
        <StatCard
          icon={<Clock size={16} />}
          label="Avg Latency"
          value={summary?.avg_latency_ms ? `${summary.avg_latency_ms.toFixed(0)}ms` : '—'}
          sub={summary?.p95_latency_ms ? `P95: ${summary.p95_latency_ms.toFixed(0)}ms` : undefined}
          color="cyan"
        />
        <StatCard
          icon={<AlertTriangle size={16} />}
          label="Error Rate"
          value={summary ? `${(summary.error_rate * 100).toFixed(1)}%` : '—'}
          sub={`${summary?.error_count ?? 0} errors`}
          color={summary && summary.error_rate > 0.05 ? 'red' : 'green'}
        />
        <StatCard
          icon={<Cpu size={16} />}
          label="Total Tokens"
          value={summary?.total_tokens ? `${(summary.total_tokens / 1000).toFixed(1)}k` : '—'}
          sub="All providers"
          color="yellow"
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Latency over time */}
        <div className="lg:col-span-2 bg-gray-900 border border-gray-800 rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp size={14} className="text-brand-400" />
            <h3 className="text-sm font-semibold text-white">Latency Over Time</h3>
          </div>
          {latency.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={latency}>
                <defs>
                  <linearGradient id="latencyGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis
                  dataKey="timestamp"
                  tick={{ fontSize: 10, fill: '#6b7280' }}
                  tickFormatter={(v) => new Date(v).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                />
                <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} unit="ms" />
                <Tooltip
                  contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8, fontSize: 12 }}
                  labelFormatter={(v) => new Date(v).toLocaleString()}
                  formatter={(v: number) => [`${v.toFixed(0)}ms`, 'Avg Latency']}
                />
                <Area
                  type="monotone"
                  dataKey="avg_latency_ms"
                  stroke="#6366f1"
                  strokeWidth={2}
                  fill="url(#latencyGrad)"
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-48 flex items-center justify-center text-gray-600 text-sm">
              No data yet — send some messages first
            </div>
          )}
        </div>

        {/* Provider distribution */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Zap size={14} className="text-yellow-400" />
            <h3 className="text-sm font-semibold text-white">By Provider</h3>
          </div>
          {providerPieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={providerPieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {providerPieData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8, fontSize: 12 }}
                />
                <Legend iconSize={8} wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-48 flex items-center justify-center text-gray-600 text-sm">No data yet</div>
          )}
        </div>
      </div>

      {/* Provider stats table */}
      {providerStats.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
          <h3 className="text-sm font-semibold text-white mb-4">Provider Performance</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-gray-500 border-b border-gray-800">
                  <th className="text-left pb-2 font-medium">Provider</th>
                  <th className="text-left pb-2 font-medium">Model</th>
                  <th className="text-right pb-2 font-medium">Requests</th>
                  <th className="text-right pb-2 font-medium">Success Rate</th>
                  <th className="text-right pb-2 font-medium">Avg Latency</th>
                  <th className="text-right pb-2 font-medium">Tokens</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {providerStats.map((s, i) => (
                  <tr key={i} className="text-gray-300">
                    <td className="py-2 font-medium text-white">{s.provider}</td>
                    <td className="py-2 text-gray-400 font-mono">{s.model}</td>
                    <td className="py-2 text-right">{s.total_requests}</td>
                    <td className="py-2 text-right">
                      <span className={s.success_rate > 0.95 ? 'text-green-400' : 'text-yellow-400'}>
                        {(s.success_rate * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="py-2 text-right">{s.avg_latency_ms.toFixed(0)}ms</td>
                    <td className="py-2 text-right">{(s.total_tokens / 1000).toFixed(1)}k</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Recent logs */}
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
        <h3 className="text-sm font-semibold text-white mb-4">Recent Inference Logs</h3>
        {recentLogs.length > 0 ? (
          <div className="space-y-2">
            {recentLogs.map((log) => (
              <div
                key={log.id}
                className="flex items-center gap-3 px-3 py-2 rounded-lg bg-gray-800/50 text-xs"
              >
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                  log.status === 'success' ? 'bg-green-400' : 'bg-red-400'
                }`} />
                <span className="text-gray-400 font-mono w-16 shrink-0">{log.provider}</span>
                <span className="text-gray-500 truncate flex-1">{log.model}</span>
                <span className="text-gray-400 shrink-0">
                  {log.latency_ms ? `${log.latency_ms.toFixed(0)}ms` : '—'}
                </span>
                <span className="text-gray-500 shrink-0">
                  {log.total_tokens ? `${log.total_tokens}t` : '—'}
                </span>
                {log.is_streaming && (
                  <span className="text-brand-400 shrink-0">stream</span>
                )}
                <span className="text-gray-600 shrink-0">
                  {formatDistanceToNow(new Date(log.created_at), { addSuffix: true })}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-600 text-center py-8">
            No inference logs yet — start chatting to see data here.
          </p>
        )}
      </div>
    </div>
  )
}
