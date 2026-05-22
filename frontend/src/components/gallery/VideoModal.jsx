import { X } from 'lucide-react'
import { useEffect } from 'react'

export default function VideoModal({ video, onClose }) {
  useEffect(() => {
    function onKey(e) { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const date = video.created_at
    ? new Date(video.created_at).toLocaleDateString('he-IL', { day: 'numeric', month: 'long', year: 'numeric' })
    : ''

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="relative w-full max-w-2xl rounded-2xl bg-zinc-900 border border-zinc-800 overflow-hidden shadow-2xl">
        <button
          onClick={onClose}
          className="absolute top-3 left-3 z-10 p-1.5 rounded-lg bg-zinc-950/80 text-zinc-400 hover:text-white"
        >
          <X size={18} />
        </button>

        <video
          src={video.video_url}
          controls
          autoPlay
          className="w-full max-h-[70vh] object-contain bg-black"
        />

        <div className="p-5 space-y-2">
          <h2 className="text-lg font-semibold text-white">{video.title || video.product_name}</h2>
          {video.product_name && video.title !== video.product_name && (
            <p className="text-sm text-zinc-400">{video.product_name}</p>
          )}
          {video.description && (
            <p className="text-sm text-zinc-400 leading-relaxed">{video.description}</p>
          )}
          {date && <p className="text-xs text-zinc-600">{date}</p>}
          {video.hashtags?.length > 0 && (
            <div className="flex flex-wrap gap-1.5 pt-1">
              {video.hashtags.map(tag => (
                <span key={tag} className="text-xs px-2 py-0.5 rounded-full bg-zinc-800 text-indigo-400">
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
