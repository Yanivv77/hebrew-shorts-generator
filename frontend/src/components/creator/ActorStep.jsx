import { useState } from 'react'
import { getActorOptions, uploadActor } from '../../lib/api'
import { useApiKeys } from '../../hooks/useApiKeys'
import Spinner from '../shared/Spinner'
import { Upload } from 'lucide-react'

export default function ActorStep({ script, onComplete }) {
  const { keys } = useApiKeys()
  const [images, setImages] = useState([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [selected, setSelected] = useState(null)
  const [error, setError] = useState(null)

  async function generate() {
    setError(null)
    setLoading(true)
    try {
      const res = await getActorOptions({ actorDescription: script.actor_description }, keys)
      setImages(res.images || [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const res = await uploadActor(file)
      const url = res.url
      setImages(prev => [url, ...prev])
      setSelected(url)
    } catch (e) {
      setError(e.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-white mb-1">בחירת שחקן</h2>
        <p className="text-sm text-zinc-400">
          תיאור שחקן: <span className="text-zinc-300">{script?.actor_description}</span>
        </p>
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          onClick={generate}
          disabled={loading}
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium transition-colors"
        >
          {loading && <Spinner size="sm" />}
          {loading ? 'יוצר...' : 'צור אפשרויות שחקן'}
        </button>

        <label className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-sm font-medium cursor-pointer transition-colors">
          {uploading ? <Spinner size="sm" /> : <Upload size={16} />}
          העלה תמונה שלך
          <input type="file" accept="image/*" className="hidden" onChange={handleUpload} disabled={uploading} />
        </label>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {loading && images.length === 0 && (
        <div className="grid grid-cols-3 gap-3">
          {[0, 1, 2].map(i => (
            <div key={i} className="aspect-square rounded-xl bg-zinc-800 animate-pulse" />
          ))}
        </div>
      )}

      {images.length > 0 && (
        <div className="grid grid-cols-3 gap-3">
          {images.map((url, i) => (
            <button
              key={i}
              onClick={() => setSelected(url)}
              className={`aspect-square rounded-xl overflow-hidden border-2 transition-all ${
                selected === url ? 'border-indigo-500 scale-[1.02]' : 'border-transparent hover:border-zinc-600'
              }`}
            >
              <img src={url} alt={`שחקן ${i + 1}`} className="w-full h-full object-cover" />
            </button>
          ))}
        </div>
      )}

      <button
        onClick={() => onComplete(selected)}
        disabled={!selected}
        className="px-6 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium transition-colors"
      >
        המשך
      </button>
    </div>
  )
}
