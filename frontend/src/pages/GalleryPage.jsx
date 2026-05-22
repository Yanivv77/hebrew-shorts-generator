import { useEffect, useState } from 'react'
import { Helmet } from 'react-helmet-async'
import { getGallery } from '../lib/api'
import VideoCard from '../components/gallery/VideoCard'
import VideoModal from '../components/gallery/VideoModal'
import Spinner from '../components/shared/Spinner'

const PAGE_SIZE = 20

export default function GalleryPage() {
  const [videos, setVideos] = useState([])
  const [visible, setVisible] = useState(PAGE_SIZE)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    getGallery()
      .then(setVideos)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <>
      <Helmet>
        <title>גלריית שורטס בעברית</title>
        <meta name="description" content="סרטוני UGC קצרים שנוצרו בבינה מלאכותית עבור מוצרי SaaS" />
      </Helmet>

      <div className="max-w-6xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-white mb-6">גלריה</h1>

        {loading && (
          <div className="flex justify-center py-16">
            <Spinner size="lg" />
          </div>
        )}

        {error && (
          <p className="text-red-400 text-center py-8">{error}</p>
        )}

        {!loading && !error && videos.length === 0 && (
          <p className="text-zinc-500 text-center py-16">אין סרטונים בגלריה עדיין</p>
        )}

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {videos.slice(0, visible).map(v => (
            <VideoCard key={v.id} video={v} onClick={() => setSelected(v)} />
          ))}
        </div>

        {visible < videos.length && (
          <div className="flex justify-center mt-8">
            <button
              onClick={() => setVisible(v => v + PAGE_SIZE)}
              className="px-6 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-sm text-white transition-colors"
            >
              טען עוד
            </button>
          </div>
        )}
      </div>

      {selected && <VideoModal video={selected} onClose={() => setSelected(null)} />}
    </>
  )
}
