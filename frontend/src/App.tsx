import { Sidebar } from './components/sidebar/Sidebar'
import { ChatWindow } from './components/chat/ChatWindow'
import { Dashboard } from './components/dashboard/Dashboard'
import { useStore } from './store'

export default function App() {
  const { activeTab } = useStore()

  return (
    <div className="flex h-screen bg-gray-950 overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-hidden">
        {activeTab === 'chat' ? <ChatWindow /> : <Dashboard />}
      </main>
    </div>
  )
}
