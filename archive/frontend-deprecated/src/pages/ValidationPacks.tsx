import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { listPacks, listProjects, deletePack, createPack } from '../api/client'
import { useApi } from '../hooks/useApi'
import {
  Screen, Card, Row, Col, Display, Text, Eyebrow, Pill, Button,
  Meter, LoadingSpinner, ErrorBanner, EmptyState,
} from '../design/components'
import { P, F } from '../design/tokens'
import type { ValidationPackCreate } from '../api/types'

function NewPackModal({ projectId, onClose, onCreated }: {
  projectId: string; onClose: () => void; onCreated: () => void
}) {
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const save = async () => {
    if (!name.trim()) return
    setSaving(true)
    try {
      await createPack({ project_id: projectId, name: name.trim(), description: desc.trim() } as ValidationPackCreate)
      onCreated()
      onClose()
    } catch (e: any) { setError(e.message) }
    finally { setSaving(false) }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    }} onClick={onClose}>
      <Card pad={28} style={{ width: 420 }} onClick={(e) => e.stopPropagation()}>
        <Display size={18} weight={600} style={{ marginBottom: 20 }}>New validation pack</Display>
        {error && <div style={{ marginBottom: 12 }}><ErrorBanner message={error} /></div>}
        <Col gap={14}>
          <Col gap={6}>
            <Text size={12} color={P.textDim}>Name</Text>
            <input autoFocus value={name} onChange={e => setName(e.target.value)}
              placeholder="Login flow validation"
              style={{ background: P.cardHi, border: `1px solid ${P.border}`, borderRadius: 8, padding: '8px 12px', color: P.text, fontFamily: F.ui, fontSize: 13, outline: 'none', width: '100%' }} />
          </Col>
          <Col gap={6}>
            <Text size={12} color={P.textDim}>Description (optional)</Text>
            <textarea value={desc} onChange={e => setDesc(e.target.value)} rows={2}
              style={{ background: P.cardHi, border: `1px solid ${P.border}`, borderRadius: 8, padding: '8px 12px', color: P.text, fontFamily: F.ui, fontSize: 13, outline: 'none', width: '100%', resize: 'none' }} />
          </Col>
          <Row gap={8} style={{ justifyContent: 'flex-end', marginTop: 4 }}>
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button variant="primary" onClick={save} disabled={saving || !name.trim()}>
              {saving ? 'Creating…' : 'Create pack'}
            </Button>
          </Row>
        </Col>
      </Card>
    </div>
  )
}

export default function ValidationPacks() {
  const nav = useNavigate()
  const [params] = useSearchParams()
  const filterProjectId = params.get('project_id') ?? undefined
  const [showNew, setShowNew] = useState(false)
  const { data: projects } = useApi(listProjects)
  const { data: packs, loading, error, refetch } = useApi(
    () => listPacks(filterProjectId), [filterProjectId ?? '']
  )

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this validation pack?')) return
    await deletePack(id).catch(() => {})
    refetch()
  }

  const activeProject = projects?.find(p => p.id === filterProjectId)

  return (
    <Screen
      title="Validation Packs"
      sub={packs ? `${packs.length} pack${packs.length !== 1 ? 's' : ''}${activeProject ? ` in ${activeProject.name}` : ''}` : undefined}
      right={
        <Row gap={8}>
          <Button variant="ghost" onClick={refetch}>↻</Button>
          {filterProjectId && (
            <Button variant="primary" icon="+" onClick={() => setShowNew(true)}>New pack</Button>
          )}
        </Row>
      }
    >
      {showNew && filterProjectId && (
        <NewPackModal
          projectId={filterProjectId}
          onClose={() => setShowNew(false)}
          onCreated={refetch}
        />
      )}

      {loading ? <LoadingSpinner /> : error ? <ErrorBanner message={error} /> : !packs?.length ? (
        <EmptyState
          message={filterProjectId ? 'No packs in this project yet.' : 'No validation packs yet. Select a project to create one.'}
          action={filterProjectId
            ? <Button variant="primary" icon="+" onClick={() => setShowNew(true)}>New pack</Button>
            : <Button variant="ghost" onClick={() => nav('/projects')}>Go to Projects →</Button>
          }
        />
      ) : (
        <Card pad={0}>
          {/* Table header */}
          <div style={{
            display: 'grid', gridTemplateColumns: '2fr 1fr 100px 80px 80px 90px',
            padding: '10px 20px',
            borderBottom: `1px solid ${P.border}`,
          }}>
            {['Pack', 'Project', 'Steps', 'Coverage', 'Created', ''].map((h, i) => (
              <Eyebrow key={i}>{h}</Eyebrow>
            ))}
          </div>

          {packs.map((pack, idx) => {
            const proj = projects?.find(p => p.id === pack.project_id)
            const stepCount = pack.steps?.length ?? 0
            const coverage = Math.min(100, stepCount * 10) // indicative
            return (
              <div
                key={pack.id}
                onClick={() => nav(`/packs/${pack.id}`)}
                style={{
                  display: 'grid', gridTemplateColumns: '2fr 1fr 100px 80px 80px 90px',
                  padding: '14px 20px', alignItems: 'center',
                  borderBottom: idx < packs.length - 1 ? `1px solid ${P.border}` : 'none',
                  cursor: 'pointer',
                  transition: 'background 0.1s',
                }}
                onMouseEnter={e => (e.currentTarget.style.background = P.cardHi)}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              >
                {/* Pack name + desc */}
                <Col gap={2}>
                  <Text size={13} weight={500}>{pack.name}</Text>
                  {pack.description && <Text size={11} color={P.textMute}>{pack.description}</Text>}
                </Col>

                {/* Project */}
                <Text size={12} color={P.textDim}>{proj?.name ?? pack.project_id.slice(0, 8)}</Text>

                {/* Steps */}
                <Row gap={6} style={{ alignItems: 'center' }}>
                  <Text size={13} mono>{stepCount}</Text>
                  <Text size={11} color={P.textMute}>step{stepCount !== 1 ? 's' : ''}</Text>
                </Row>

                {/* Coverage meter */}
                <div style={{ width: 60 }}>
                  <Meter value={coverage} color={P.accent} height={4} />
                </div>

                {/* Created */}
                <Text size={11} color={P.textMute} mono>
                  {new Date(pack.created_at).toLocaleDateString()}
                </Text>

                {/* Actions */}
                <Row gap={6} onClick={(e) => e.stopPropagation()}>
                  <Button size="sm" variant="primary" onClick={() => nav(`/packs/${pack.id}`)}>Open</Button>
                  <Button size="sm" variant="danger" onClick={() => handleDelete(pack.id)}>×</Button>
                </Row>
              </div>
            )
          })}
        </Card>
      )}
    </Screen>
  )
}
