import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { Settings } from 'lucide-react'
import ApiKeyModal from './shared/ApiKeyModal'
import { useApiKeys } from '../hooks/useApiKeys'

export default function Navbar() {
  const [showKeys, setShowKeys] = useState(false)
  const { keys, updateKey } = useApiKeys()

  const linkClass = ({ isActive }) =>
    `px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
      isActive ? 'bg-zinc-800 text-white' : 'text-zinc-400 hover:text-white'
    }`

  return (
    <>
      <nav className="flex items-center justify-between px-6 py-3 border-b border-zinc-800 bg-zinc-950">
        <span className="text-lg font-bold text-white tracking-tight">שורטס</span>
        <div className="flex items-center gap-1">
          <NavLink to="/" end className={linkClass}>יוצר</NavLink>
          <NavLink to="/gallery" className={linkClass}>גלריה</NavLink>
        </div>
        <button
          onClick={() => setShowKeys(true)}
          className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
          title="הגדרות API"
        >
          <Settings size={18} />
        </button>
      </nav>
      {showKeys && (
        <ApiKeyModal keys={keys} onUpdate={updateKey} onClose={() => setShowKeys(false)} />
      )}
    </>
  )
}
