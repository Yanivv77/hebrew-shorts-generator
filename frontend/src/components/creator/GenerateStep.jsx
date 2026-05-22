import { useState, useEffect, useRef } from 'react'
import { generateVideo, getJobStatus } from '../../lib/api'
import { useApiKeys } from '../../hooks/useApiKeys'
import Spinner from '../shared/Spinner'

const VOICES = [
  { id: 'pFZP5JQG7iQjIQuC4Bku', name: 'Lily', language: 'he' },
  { id: 'TX3LPaxmHKxFdv7VOQHJ', name: 'Liam', language: 'he' },
  { id: 'EXAVITQu4vr4xnSDxMaL', name: 'Sarah', language: 'he' },
  { id: '21m00Tcm4TlvDq8ikWAM', name: 'Rachel', language: 'multi' },
  { id: 'AZnzlk1XvdvUeBnXmlld', name: 'Domi', language: 'multi' },
  { id: 'MF3mGyEYCl7XYWbV9V6O', name: 'Elli', language: 'multi' },
  { id: 'TxGEqnHWrfWFTfGW9XjX', name: 'Josh', language: 'multi' },
]

const MODES = [
  { value: 'lowcost', label: 'חסכוני', cost: '~$0.40' },
  { value: 'premium', label: 'פרמיום', cost: '~$1.70' },
]

export default function GenerateStep({ scripts, selectedScript, actorImageUrl, onComplete }) {
  const { keys } = useApiKeys()
  const [voiceId, setVoiceId] = useState(VOICES[0].id)
  const [videoMode, setVideoMode] = useState('lowcost')
  const [loading, setLoading] = useState(false)
  const [logs, setLogs] = useState([])
  const [, setStatus] = useState(null)
  const [jobId, setJobId] = useState(null)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const logsEndRef = useRef(null)
  const pollRef = useRef(null)

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  useEffect(() => () => clearInterval(pollRef.current), [])

  async function startGeneration() {
    setError(null)
    setLoading(true)
    setLogs([])
    setStatus('queued')

    const scriptIndex = scripts.indexOf(selectedScript)

    try {
      const res = await generateVideo({
        script_index: scriptIndex >= 0 ? scriptIndex : 0,
        scripts,
        actor_image_url: actorImageUrl,
        voice_id: voiceId,
        video_mode: videoMode,
        product_name: selectedScript?.title || '',
      }, keys)

      const id = res.job_id
      setJobId(id)

      pollRef.current = setInterval(async () => {
        try {
          const job = await getJobStatus(id)
          setLogs(job.logs || [])
          setStatus(job.status)
          if (job.status === 'completed' || job.status === 'failed') {
            clearInterval(pollRef.current)
            setLoading(false)
            if (job.status === 'completed') {
              setResult(job.result)
            } else {
              setError('יצירת הסרטון נכשלה')
            }
          }
        } catch (e) {
          clearInterval(pollRef.current)
          setLoading(false)
          setError(e.message)
        }
      }, 2000)
    } catch (e) {
      setLoading(false)
      setError(e.message)
    }
  }

  const selectedMode = MODES.find(m => m.value === videoMode)

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-white mb-1">יצירת וידאו</h2>
        <p className="text-sm text-zinc-400">בחר קול ומצב וידאו</p>
      </div>

      <div>
        <p className="text-xs text-zinc-400 mb-2">קול</p>
        <select
          value={voiceId}
          onChange={e => setVoiceId(e.target.value)}
          className="w-full rounded-lg bg-zinc-900 border border-zinc-700 px-3 py-2.5 text-white text-sm focus:outline-none focus:border-indigo-500 appearance-none"
        >
          <optgroup label="עברית">
            {VOICES.filter(v => v.language === 'he').map(v => (
              <option key={v.id} value={v.id}>{v.name}</option>
            ))}
          </optgroup>
          <optgroup label="רב-לשוני">
            {VOICES.filter(v => v.language === 'multi').map(v => (
              <option key={v.id} value={v.id}>{v.name}</option>
            ))}
          </optgroup>
        </select>
      </div>

      <div>
        <p className="text-xs text-zinc-400 mb-2">מצב וידאו</p>
        <div className="flex gap-2">
          {MODES.map(m => (
            <button
              key={m.value}
              onClick={() => setVideoMode(m.value)}
              className={`flex-1 py-2.5 rounded-lg text-sm font-medium border transition-colors ${
                videoMode === m.value
                  ? 'border-indigo-500 bg-indigo-600/20 text-white'
                  : 'border-zinc-700 bg-zinc-900 text-zinc-400 hover:text-white'
              }`}
            >
              {m.label}
              <span className="block text-xs mt-0.5 font-normal text-zinc-400">{m.cost}</span>
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-zinc-500">
          עלות משוערת: <span className="text-zinc-300">{selectedMode.cost}</span>
        </p>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {!result && (
        <button
          onClick={startGeneration}
          disabled={loading}
          className="flex items-center gap-2 px-6 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium transition-colors"
        >
          {loading && <Spinner size="sm" />}
          {loading ? 'יוצר...' : 'צור וידאו'}
        </button>
      )}

      {(logs.length > 0 || loading) && (
        <div className="rounded-xl bg-zinc-950 border border-zinc-800 p-4 max-h-48 overflow-y-auto font-mono text-xs space-y-1">
          {logs.map((l, i) => (
            <div key={i} className="text-zinc-400">
              <span className="text-zinc-600">{new Date(l.time * 1000).toLocaleTimeString('he-IL')}</span>
              {' '}
              <span>{l.msg}</span>
            </div>
          ))}
          {loading && (
            <div className="flex items-center gap-2 text-zinc-500">
              <Spinner size="sm" />
              <span>מעבד...</span>
            </div>
          )}
          <div ref={logsEndRef} />
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <video
            src={result.video_url}
            controls
            className="w-full rounded-xl border border-zinc-800"
          />
          <button
            onClick={() => onComplete(jobId, result)}
            className="w-full py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition-colors"
          >
            המשך לשיתוף
          </button>
        </div>
      )}
    </div>
  )
}
