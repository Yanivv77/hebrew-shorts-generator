export default function VideoCard({ video, onClick }) {
  const date = video.created_at
    ? new Date(video.created_at).toLocaleDateString('he-IL', { day: 'numeric', month: 'short', year: 'numeric' })
    : ''

  return (
    <button
      onClick={onClick}
      className="group rounded-xl overflow-hidden bg-zinc-900 border border-zinc-800 hover:border-zinc-600 transition-all text-right"
    >
      <div className="aspect-[9/16] bg-zinc-800 overflow-hidden">
        {video.thumbnail_url ? (
          <img
            src={video.thumbnail_url}
            alt={video.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-zinc-600 text-xs">
            אין תמונה
          </div>
        )}
      </div>
      <div className="p-3">
        <p className="text-white text-sm font-medium line-clamp-1">{video.product_name || video.title}</p>
        {date && <p className="text-zinc-500 text-xs mt-0.5">{date}</p>}
      </div>
    </button>
  )
}
