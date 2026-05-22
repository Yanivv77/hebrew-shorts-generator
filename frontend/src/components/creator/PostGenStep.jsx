import { useState } from 'react'
import { socialPost } from '../../lib/api'
import { useApiKeys } from '../../hooks/useApiKeys'
import { Download, Share2, CheckCircle, X } from 'lucide-react'
import Spinner from '../shared/Spinner'

const PLATFORMS = [
  { id: 'tiktok', label: 'TikTok' },
  { id: 'instagram', label: 'Instagram' },
  { id: 'youtube', label: 'YouTube' },
]

function SocialModal({ script, onClose, keys }) {
  const [platforms, setPlatforms] = useState(['tiktok'])
  const [caption, setCaption] = useState(script?.caption || '')
  const [scheduleDate, setScheduleDate] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState(null)

  function togglePlatform(id) {
    setPlatforms(prev =>
      prev.includes(id) ? prev.filter(p => p !== id) : [...prev, id]
    )
  }

  async function post() {
    setError(null)
    setLoading(true)
    try {
      await socialPost({ platforms, caption, scheduled_date: scheduleDate || undefined }, keys)
      setDone(true)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-xl bg-zinc-900 border border-zinc-800 p-6 shadow-2xl">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-white">שיתוף ברשתות חברתיות</h2>
          <button onClick={onClose} className="text-zinc-400 hover:text-white"><X size={20} /></button>
        </div>

        {done ? (
          <div className="flex flex-col items-center gap-3 py-6">
            <CheckCircle size={40} className="text-green-500" />
            <p className="text-white font-medium">הסרטון נשלח בהצלחה!</p>
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <p className="text-xs text-zinc-400 mb-2">פלטפורמות</p>
              <div className="flex gap-2">
                {PLATFORMS.map(p => (
                  <button
                    key={p.id}
                    onClick={() => togglePlatform(p.id)}
                    className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                      platforms.includes(p.id)
                        ? 'border-indigo-500 bg-indigo-600/20 text-white'
                        : 'border-zinc-700 text-zinc-400 hover:text-white'
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <p className="text-xs text-zinc-400 mb-2">כיתוב</p>
              <textarea
                value={caption}
                onChange={e => setCaption(e.target.value)}
                rows={3}
                className="w-full rounded-lg bg-zinc-800 border border-zinc-700 px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 resize-none"
              />
            </div>

            <div>
              <p className="text-xs text-zinc-400 mb-2">תזמון (אופציונלי)</p>
              <input
                type="datetime-local"
                value={scheduleDate}
                onChange={e => setScheduleDate(e.target.value)}
                className="w-full rounded-lg bg-zinc-800 border border-zinc-700 px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
              />
            </div>

            {error && <p className="text-red-400 text-sm">{error}</p>}

            <button
              onClick={post}
              disabled={loading || platforms.length === 0}
              className="flex items-center justify-center gap-2 w-full py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium transition-colors"
            >
              {loading && <Spinner size="sm" />}
              {loading ? 'שולח...' : 'פרסם'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default function PostGenStep({ jobResult, selectedScript }) {
  const { keys } = useApiKeys()
  const [showSocial, setShowSocial] = useState(false)

  if (!jobResult) return null

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-white mb-1">הסרטון מוכן!</h2>
        <p className="text-sm text-zinc-400">הורד, הוסף לגלריה או שתף ברשתות</p>
      </div>

      <video
        src={jobResult.video_url}
        controls
        className="w-full rounded-xl border border-zinc-800"
      />

      <div className="flex flex-wrap gap-3">
        <a
          href={jobResult.video_url}
          download
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-white text-sm font-medium transition-colors"
        >
          <Download size={16} />
          הורד
        </a>

        <div className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-zinc-800 text-sm">
          {jobResult.gallery_id ? (
            <>
              <CheckCircle size={16} className="text-green-500" />
              <span className="text-zinc-300">בגלריה</span>
            </>
          ) : (
            <span className="text-zinc-500">לא הועלה לגלריה</span>
          )}
        </div>

        <button
          onClick={() => setShowSocial(true)}
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors"
        >
          <Share2 size={16} />
          שתף ברשתות
        </button>
      </div>

      {showSocial && (
        <SocialModal
          script={selectedScript}
          onClose={() => setShowSocial(false)}
          keys={keys}
        />
      )}
    </div>
  )
}
