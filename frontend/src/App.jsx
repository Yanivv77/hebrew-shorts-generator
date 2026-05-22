import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import CreatorPage from './pages/CreatorPage'
import GalleryPage from './pages/GalleryPage'

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-zinc-950 text-white">
        <Navbar />
        <Routes>
          <Route path="/" element={<CreatorPage />} />
          <Route path="/gallery" element={<GalleryPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}
