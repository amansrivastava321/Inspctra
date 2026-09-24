import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { GlobalSearch, useGlobalSearch } from './components/common/GlobalSearch';
import DashboardPage from './pages/DashboardPage';
import ProjectsPage from './pages/ProjectsPage';
import AddAppPage from './pages/AddAppPage';
import AppDetailPage from './pages/AppDetailPage';
import RuntimeDoctorPage from './pages/RuntimeDoctorPage';
import ValidationPacksPage from './pages/ValidationPacksPage';
import CreateValidationPackPage from './pages/CreateValidationPackPage';
import PackDetailPage from './pages/PackDetailPage';
import LiveRunsPage from './pages/LiveRunsPage';
import LiveRunDetailPage from './pages/LiveRunDetailPage';
import EvidenceCenterPage from './pages/EvidenceCenterPage';
import ReportsPage from './pages/ReportsPage';
import ReportDetailPage from './pages/ReportDetailPage';
import ConnectorsPage from './pages/ConnectorsPage';
import ModelSettingsPage from './pages/ModelSettingsPage';
import MemoryPage from './pages/MemoryPage';
import SettingsPage from './pages/SettingsPage';
import { WorkspaceModeProvider } from './state/WorkspaceModeContext';
import { ErrorBoundary } from './components/ErrorBoundary';

function WorkspaceRoutes() {
  return (
    <Routes>
      <Route index                       element={<DashboardPage />} />
      <Route path="projects"            element={<ProjectsPage />} />
      <Route path="projects/new"        element={<AddAppPage />} />
      <Route path="apps/:appId"         element={<AppDetailPage />} />
      <Route path="doctor"              element={<RuntimeDoctorPage />} />
      <Route path="runtime-doctor"      element={<RuntimeDoctorPage />} />
      <Route path="packs"               element={<ValidationPacksPage />} />
      <Route path="packs/new"           element={<CreateValidationPackPage />} />
      <Route path="packs/:packId"       element={<PackDetailPage />} />
      <Route path="runs"                element={<LiveRunsPage />} />
      <Route path="runs/:runId"         element={<LiveRunDetailPage />} />
      <Route path="evidence"            element={<EvidenceCenterPage />} />
      <Route path="reports"             element={<ReportsPage />} />
      <Route path="reports/:reportId"   element={<ReportDetailPage />} />
      <Route path="connectors"          element={<ConnectorsPage />} />
      <Route path="models"              element={<ModelSettingsPage />} />
      <Route path="memory"              element={<MemoryPage />} />
      <Route path="settings"            element={<SettingsPage />} />
      <Route path="model-settings"      element={<Navigate to="../models" replace />} />
      <Route path="*"                   element={<Navigate to="." replace />} />
    </Routes>
  );
}

function WorkspaceBoundary({ mode }: { mode: 'real' | 'demo' }) {
  const { open, close } = useGlobalSearch();
  return (
    <WorkspaceModeProvider mode={mode}>
      <GlobalSearch open={open} onClose={close} />
      <WorkspaceRoutes />
    </WorkspaceModeProvider>
  );
}

function AppWithSearch() {
  return (
    <Routes>
      <Route path="/demo/*" element={<WorkspaceBoundary mode="demo" />} />
      <Route path="/*" element={<WorkspaceBoundary mode="real" />} />
    </Routes>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AppWithSearch />
      </BrowserRouter>
    </ErrorBoundary>
  );
}
