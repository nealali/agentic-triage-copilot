import { Routes, Route, Link, useLocation } from 'react-router-dom'
import Upload from './pages/Upload'
import IssuesList from './pages/IssuesList'
import IssueDetail from './pages/IssueDetail'
import Audit from './pages/Audit'

function Layout({ children }: { children: React.ReactNode }) {
  const loc = useLocation()
  const setApiKey = () => {
    const key = window.prompt('API key (stored in session only). Leave empty to clear.')
    if (key !== null) {
      if (key) sessionStorage.setItem('apiKey', key)
      else sessionStorage.removeItem('apiKey')
      window.location.reload()
    }
  }
  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="border-b bg-white px-4 py-3 flex gap-4 items-center">
        <Link to="/" className="font-semibold text-gray-800 hover:text-blue-600">Triage Copilot</Link>
        <Link to="/" className={loc.pathname === '/' ? 'text-blue-600' : 'text-gray-600 hover:text-gray-900'}>Upload</Link>
        <Link to="/issues" className={loc.pathname === '/issues' || loc.pathname.startsWith('/issues/') ? 'text-blue-600' : 'text-gray-600 hover:text-gray-900'}>Issues</Link>
        <Link to="/audit" className={loc.pathname === '/audit' ? 'text-blue-600' : 'text-gray-600 hover:text-gray-900'}>Audit</Link>
        <button type="button" onClick={setApiKey} className="ml-auto text-sm text-gray-500 hover:text-gray-700">API key</button>
      </nav>
      <main className="max-w-5xl mx-auto p-4">{children}</main>
    </div>
  )
}

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Upload />} />
        <Route path="/issues" element={<IssuesList />} />
        <Route path="/issues/:id" element={<IssueDetail />} />
        <Route path="/audit" element={<Audit />} />
      </Routes>
    </Layout>
  )
}
