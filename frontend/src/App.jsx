import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Sidebar from './components/Sidebar'
import Accounts from './pages/Accounts'
import Groups from './pages/Groups'
import Composer from './pages/Composer'
import History from './pages/History'

export default function App() {
  return (
    <BrowserRouter>
      <Toaster position="top-right" toastOptions={{ duration: 4000 }} />
      <div style={{ display: 'flex', minHeight: '100vh' }}>
        <Sidebar />
        <main style={{ flex: 1, padding: '24px', overflowY: 'auto' }}>
          <Routes>
            <Route path="/" element={<Navigate to="/composer" replace />} />
            <Route path="/accounts" element={<Accounts />} />
            <Route path="/groups" element={<Groups />} />
            <Route path="/composer" element={<Composer />} />
            <Route path="/history" element={<History />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
