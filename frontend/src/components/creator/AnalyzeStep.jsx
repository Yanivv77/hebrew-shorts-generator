import { useState } from 'react'
import { analyzeProduct } from '../../lib/api'
import { useApiKeys } from '../../hooks/useApiKeys'
import Spinner from '../shared/Spinner'

const LANGUAGES = [
  { value: 'he', label: 'עברית' },
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Español' },
]

const PLATFORM_LABELS = { tiktok: 'TikTok', instagram: 'Instagram', youtube: 'YouTube' }
const STYLE_LABELS = { ugc: 'UGC', educational: 'חינוכי', shock: 'שוק', story: 'סיפור', comparison: 'השוואה' }

export default function AnalyzeStep({ onComplete }) {
  const { keys } = useApiKeys()
  const [inputMode, setInputMode] = useState('url')
  const [url, setUrl] = useState('')
  const [description, setDescription] = useState('')
  const [language, setLanguage] = useState('he')
  const [gender, setGender] = useState('female')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [scripts, setScripts] = useState(null)
  const [selected, setSelected] = useState(null)

  async function handleSubmit() {
    setError(null)
    setLoading(true)
    try {
      const result = await analyzeProduct({
        url: inputMode === 'url' ? url : undefined,
        description: inputMode === 'text' ? description : undefined,
        language,
        actorGender: gender,
      }, keys)
      setScripts(result.scripts)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function handleSelect(script) {
    setSelected(script)
    onComplete({ scripts }, script)
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-white mb-1">ניתוח מוצר</h2>
        <p className="text-sm text-zinc-400">הכנס URL של אתר SaaS או תיאור טקסטואלי</p>
      </div>

      <div className="flex gap-1 p-1 bg-zinc-900 rounded-lg w-fit">
        <button
          onClick={() => setInputMode('url')}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
            inputMode === 'url' ? 'bg-zinc-700 text-white' : 'text-zinc-400 hover:text-white'
          }`}
        >
          URL
        </button>
        <button
          onClick={() => setInputMode('text')}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
            inputMode === 'text' ? 'bg-zinc-700 text-white' : 'text-zinc-400 hover:text-white'
          }`}
        >
          תיאור
        </button>
      </div>

      {inputMode === 'url' ? (
        <input
          type="url"
          value={url}
          onChange={e => setUrl(e.target.value)}
          placeholder="https://example.com"
          dir="ltr"
          className="w-full rounded-lg bg-zinc-900 border border-zinc-700 px-4 py-3 text-white placeholder-zinc-600 focus:outline-none focus:border-indigo-500"
        />
      ) : (
        <textarea
          value={description}
          onChange={e => setDescription(e.target.value)}
          placeholder="תאר את המוצר שלך..."
          rows={4}
          className="w-full rounded-lg bg-zinc-900 border border-zinc-700 px-4 py-3 text-white placeholder-zinc-600 focus:outline-none focus:border-indigo-500 resize-none"
        />
      )}

      <div className="flex flex-wrap gap-4">
        <div>
          <p className="text-xs text-zinc-400 mb-2">שפה</p>
          <div className="flex gap-1">
            {LANGUAGES.map(l => (
              <button
                key={l.value}
                onClick={() => setLanguage(l.value)}
                className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                  language === l.value ? 'bg-indigo-600 text-white' : 'bg-zinc-800 text-zinc-400 hover:text-white'
                }`}
              >
                {l.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <p className="text-xs text-zinc-400 mb-2">מגדר שחקן</p>
          <div className="flex gap-1">
            {[['female', 'נקבה'], ['male', 'זכר']].map(([val, lbl]) => (
              <button
                key={val}
                onClick={() => setGender(val)}
                className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                  gender === val ? 'bg-indigo-600 text-white' : 'bg-zinc-800 text-zinc-400 hover:text-white'
                }`}
              >
                {lbl}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      <button
        onClick={handleSubmit}
        disabled={loading || (!url && !description)}
        className="flex items-center gap-2 px-6 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium transition-colors"
      >
        {loading && <Spinner size="sm" />}
        {loading ? 'מנתח...' : 'נתח מוצר'}
      </button>

      {scripts && (
        <div className="space-y-3 pt-2">
          <p className="text-sm text-zinc-400">בחר סקריפט:</p>
          {scripts.map((script, i) => (
            <button
              key={i}
              onClick={() => handleSelect(script)}
              className={`w-full text-right rounded-xl p-4 border transition-colors
                ${selected === script
                  ? 'border-indigo-500 bg-indigo-600/10'
                  : 'border-zinc-700 bg-zinc-900 hover:border-zinc-600'}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-white text-sm leading-snug">{script.hook_text}</p>
                  <p className="text-xs text-zinc-400 mt-1 line-clamp-2">{script.full_narration?.slice(0, 100)}...</p>
                </div>
                <div className="flex flex-col items-end gap-1 shrink-0">
                  <span className="text-xs px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">
                    {PLATFORM_LABELS[script.target_platform] || script.target_platform}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">
                    {STYLE_LABELS[script.style] || script.style}
                  </span>
                  <span className="text-xs text-zinc-500">{script.duration_seconds}שנ׳</span>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
