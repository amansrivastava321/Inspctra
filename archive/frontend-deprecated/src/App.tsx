import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Projects from './pages/Projects'
import RuntimeDoctor from './pages/RuntimeDoctor'
import ValidationPacks from './pages/ValidationPacks'
import PackDetail from './pages/PackDetail'
import Runs from './pages/Runs'
import RunDetail from './pages/RunDetail'
import Evidence from './pages/Evidence'
import Reports from './pages/Reports'
import Connectors from './pages/Connectors'
import Settings from './pages/Settings'

export default function App() {
  return (
    <BrowserRouter>
      <div style={{ height: '100vh', overflow: 'hidden' }}>
        <Routes>
          <Route path="/"              element={<Dashboard />} />
          <Route path="/projects"      element={<Projects />} />
          <Route path="/doctor"        element={<RuntimeDoctor />} />
          <Route path="/packs"         element={<ValidationPacks />} />
          <Route path="/packs/:packId" element={<PackDetail />} />
          <Route path="/runs"          element={<Runs />} />
          <Route path="/runs/:runId"   element={<RunDetail />} />
          <Route path="/evidence"      element={<Evidence />} />
          <Route path="/reports"       element={<Reports />} />
          <Route path="/connectors"    element={<Connectors />} />
          <Route path="/settings"      element={<Settings />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}
