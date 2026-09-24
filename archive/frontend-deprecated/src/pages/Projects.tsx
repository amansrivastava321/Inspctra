import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listProjects, createProject, deleteProject, listApps } from '../api/client'
import { useApi } from '../hooks/useApi'
import {
  Screen, Card, Row, Col, Display, Text, Eyebrow, Pill, Button,
  LoadingSpinner, ErrorBanner, EmptyState,
} from '../design/components'
import { P, F } from '../design/tokens'
import type { Project, AppTarget } from '../api/types'

const APP_TYPE_COLORS: Record<string, string> = {
  web: P.accent, android: P.pass, ios: P.unclear,
  native_macos: P.textDim, native_windows: P.textDim,
  backend_fastapi: '#c084fc', backend_node: '#86efac',
}

function ProjectCard({ project, apps, onDelete }: { project: Project; apps: AppTarget[]; onDelete: () => void }) {
  const nav = useNavigate()
  const myApps = apps.filter(a => a.project_id === project.id)
  return (
    <Card style={{ cursor: 'pointer' }} onClick={() => nav(`/packs?project_id=${project.id}`)}>
      <Row style={{ justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <div style={{
          width: 40, height: 40, borderRadius: 10,
          background: `linear-gradient(135deg, ${P.accent}33, ${P.accentSoft})`,
          border: `1px solid ${P.accent}22`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: F.display, fontWeight: 700, fontSize: 16, color: P.accent,
        }}>
          {project.name[0].toUpperCase()}
        </div>
        <Button variant="danger" size="sm" onClick={(e) => { e.stopPropagation(); onDelete() }}>×</Button>
      </Row>
      <Display size={16} weight={600} style={{ marginBottom: 4 }}>{project.name}</Display>
      {project.description && <Text size={12} color={P.textDim} style={{ marginBottom: 10 }}>{project.description}</Text>}
      <Row gap={6} style={{ flexWrap: 'wrap', marginBottom: 10 }}>
        {project.tags.map(tag => (
          <span key={tag} style={{
            padding: '2px 8px', borderRadius: 99,
            fontFamily: F.mono, fontSize: 10,
            background: P.cardHi, border: `1px solid ${P.border}`,
            color: P.textDim,
          }}>{tag}</span>
        ))}
      </Row>
      <Row style={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <Text size={11} color={P.textMute}>{myApps.length} app{myApps.length !== 1 ? 's' : ''}</Text>
        <Row gap={4}>
          {myApps.slice(0, 3).map(a => (
            <span key={a.id} style={{
              padding: '2px 7px', borderRadius: 99,
              fontFamily: F.mono, fontSize: 9.5,
              background: `${APP_TYPE_COLORS[a.app_type] || P.textMute}1a`,
              border: `1px solid ${APP_TYPE_COLORS[a.app_type] || P.textMute}33`,
              color: APP_TYPE_COLORS[a.app_type] || P.textMute,
            }}>{a.app_type}</span>
          ))}
        </Row>
      </Row>
    </Card>
  )
}

function NewProjectModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const save = async () => {
    if (!name.trim()) return
    setSaving(true)
    try {
      await createProject({ name: name.trim(), description: desc.trim() })
      onCreated()
      onClose()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 1000,
    }} onClick={onClose}>
      <Card pad={28} style={{ width: 420 }} onClick={(e) => e.stopPropagation()}>
        <Display size={18} weight={600} style={{ marginBottom: 20 }}>New project</Display>
        {error && <ErrorBanner message={error} />}
        <Col gap={14}>
          <Col gap={6}>
            <Text size={12} color={P.textDim}>Name</Text>
            <input
              autoFocus value={name} onChange={e => setName(e.target.value)}
              placeholder="My project"
              style={{
                background: P.cardHi, border: `1px solid ${P.border}`,
                borderRadius: 8, padding: '8px 12px', color: P.text,
                fontFamily: F.ui, fontSize: 13, outline: 'none', width: '100%',
              }}
            />
          </Col>
          <Col gap={6}>
            <Text size={12} color={P.textDim}>Description (optional)</Text>
            <textarea
              value={desc} onChange={e => setDesc(e.target.value)}
              rows={2}
              style={{
                background: P.cardHi, border: `1px solid ${P.border}`,
                borderRadius: 8, padding: '8px 12px', color: P.text,
                fontFamily: F.ui, fontSize: 13, outline: 'none', width: '100%', resize: 'none',
              }}
            />
          </Col>
          <Row gap={8} style={{ justifyContent: 'flex-end', marginTop: 4 }}>
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button variant="primary" onClick={save} disabled={saving || !name.trim()}>
              {saving ? 'Creating…' : 'Create project'}
            </Button>
          </Row>
        </Col>
      </Card>
    </div>
  )
}

export default function Projects() {
  const [showNew, setShowNew] = useState(false)
  const { data: projects, loading, error, refetch } = useApi(listProjects)
  const { data: apps, refetch: refetchApps } = useApi(listApps)

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this project?')) return
    await deleteProject(id).catch(() => {})
    refetch(); refetchApps()
  }

  return (
    <Screen
      title="Projects"
      sub={projects ? `${projects.length} project${projects.length !== 1 ? 's' : ''} in this workspace` : undefined}
      right={
        <Row gap={8}>
          <Button variant="ghost" onClick={refetch}>↻</Button>
          <Button variant="primary" icon="+" onClick={() => setShowNew(true)}>New project</Button>
        </Row>
      }
    >
      {showNew && <NewProjectModal onClose={() => setShowNew(false)} onCreated={() => { refetch(); refetchApps() }} />}

      {loading ? <LoadingSpinner /> : error ? <ErrorBanner message={error} /> : !projects?.length ? (
        <EmptyState
          message="No projects yet. Create one to get started."
          action={<Button variant="primary" icon="+" onClick={() => setShowNew(true)}>New project</Button>}
        />
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: 16,
        }}>
          {projects.map(p => (
            <ProjectCard
              key={p.id} project={p}
              apps={apps || []}
              onDelete={() => handleDelete(p.id)}
            />
          ))}
        </div>
      )}
    </Screen>
  )
}
