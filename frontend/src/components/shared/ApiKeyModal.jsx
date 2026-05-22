import { useState } from 'react'
import { X } from 'lucide-react'

const FIELDS = [
  { key: 'gemini', label: 'Gemini API Key', placeholder: 'AIza...' },
  { key: 'fal', label: 'FAL API Key', placeholder: 'fal-...' },
  { key: 'elevenlabs', label: 'ElevenLabs API Key', placeholder: 'sk_...' },
  { key: 'upload_post_key', label: 'Upload-Post API Key', placeholder: 'your-key' },
  { key: 'upload_post_user', label: 'Upload-Post User ID', placeholder: 'user-id' },
]

export default function ApiKeyModal({ keys, onUpdate, onClose }) {
  const [local, setLocal] = useState({ ...keys })

  function save() {
    FIELDS.forEach(f => onUpdate(f.key, local[f.key] || ''))
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-xl bg-zinc-900 border border-zinc-800 p-6 shadow-2xl">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-white">הגדרות מפתחות API</h2>
          <button onClick={onClose} className="text-zinc-400 hover:text-white">
            <X size={20} />
          </button>
        </div>
        <div className="space-y-4">
          {FIELDS.map(({ key, label, placeholder }) => (
            <div key={key}>
              <label className="block text-sm text-zinc-400 mb-1">{label}</label>
              <input
                type="password"
                value={local[key] || ''}
                placeholder={placeholder}
                onChange={e => setLocal(prev => ({ ...prev, [key]: e.target.value }))}
                className="w-full rounded-lg bg-zinc-800 border border-zinc-700 px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-indigo-500"
              />
            </div>
          ))}
        </div>
        <button
          onClick={save}
          className="mt-6 w-full rounded-lg bg-indigo-600 hover:bg-indigo-500 py-2 text-sm font-medium text-white transition-colors"
        >
          שמור
        </button>
      </div>
    </div>
  )
}
