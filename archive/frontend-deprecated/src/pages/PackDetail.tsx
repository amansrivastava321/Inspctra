import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getPack, listApps, runPack, listRuns, deletePack } from '../api/client'
import { useApi } from '../hooks/useApi'
import {
  Screen, Card, Row, Col, Display, Text, Eyebrow, Pill, Button,
  Meter, LoadingSpinner, ErrorBanner,
} from '../design/components'
import { P, F } from '../design/tokens'
import type { AppTarget, ValidationStep } from '../api/types'

const ACTION_COLORS: Record<string, string> = {
  navigate: P.accent,
  click: '#60a5fa',
  type: '#a78bfa',
  assert: P.pass,
  wait: P.unclear,
  screenshot: '#f472b6',
}

function StepRow({ step, idx }: { step: ValidationStep; idx: number }) {
  const color = ACTION_COLORS[step.action_type] || P.textMute
  return (
    <Row style={{
      padding: '12px 20px', alignItems: 'flex-start', gap: 14,
      borderBottom: `1px solid ${P.border}`,
    }}>
      <div style={{
        width: 28, height: 28, borderRadius: 8, flexShrink: 0,
        background: `${color}22`, border: `1px solid ${color}44`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: F.mono, fontSize: 11, color,
      }}>
        {idx + 1}
      </div>
      <Col gap={4} style={{ flex: 1 }}>
        <Row gap={8} style={{ alignItems: 'center' }}>
          <span style={{
            padding: '1px 8px', borderRadius: 99,
            fontFamily: F.mono, fontSize: 10,
            background: `${color}18`, border: `1px solid ${color}33`,
            color,
          }}>{step.action_type}</span>
          <Text size={13}>{step.description}</Text>
        </Row>
        {(step.target || step.input_value || step.expected_result) && (
          <Row gap={16} style={{ flexWrap: 'wrap' }}>
            {step.target && (
              <Text size={11} mono color={P.textMute}>target: <span style={{ color: P.textDim }}>{step.target}</span></Text>
            )}
            {step.input_value && (
              <Text size={11} mono color={P.textMute}>input: <span style={{ color: P.textDim }}>"{step.input_value}"</span></Text>
            )}
            {step.expected_result && (
              <Text size={11} mono color={P.textMute}>expect: <span style={{ color: P.pass }}>{step.expected_result}</span></Text>
            )}
          </Row>
        )}
      </Col>
      <Text size={11} color={P.textMute} mono style={{ flexShrink: 0 }}>{step.timeout_seconds}s</Text>
    </Row>
  )
}

function RunModal({ packId, apps, onClose, onStarted }: {
  packId: string; apps: AppTarget[]; onClose: () => void; onStarted: (runId: string) => void
}) {
  const [appId, setAppId] = useState(apps[0]?.id ?? '')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  const start = async () => {
    if (!appId) return
    setRunning(true)
    try {
      const run = await runPack(packId, appId)
      onStarted(run.id)
      onClose()
    } catch (e: any) { setError(e.message) }
    finally { setRunning(false) }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    }} onClick={onClose}>
      <Card pad={28} style={{ width: 400 }} onClick={(e) => e.stopPropagation()}>
        <Display size={18} weight={600} style={{ marginBottom: 20 }}>Start live test run</Display>
        {error && <div style={{ marginBottom: 12 }}><ErrorBanner message={error} /></div>}
        <Col gap={14}>
          <Col gap={6}>
            <Text size={12} color={P.textDim}>App target</Text>
            <select value={appId} onChange={e => setAppId(e.target.value)} style={{
              background: P.cardHi, border: `1px solid ${P.border}`, borderRadius: 8,
              padding: '8px 12px', color: P.text, fontFamily: F.ui, fontSize: 13,
              outline: 'none', width: '100%',
            }}>
              {apps.map(a => <option key={a.id} value={a.id}>{a.name} ({a.app_type})</option>)}
            </select>
          </Col>
          {apps.length === 0 && <ErrorBanner message="No app targets available. Create one in Projects first." />}
          <Row gap={8} style={{ justifyContent: 'flex-end', marginTop: 4 }}>
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button variant="primary" icon="▸" onClick={start} disabled={running || !appId}>
              {running ? 'Starting…' : 'Start run'}
            </Button>
          </Row>
        </Col>
      </Card>
    </div>
  )
}

export default function PackDetail() {
  const { packId } = useParams<{ packId: string }>()
  const nav = useNavigate()
  const [showRun, setShowRun] = useState(false)
  const { data: pack, loading, error } = useApi(() => getPack(packId!), [packId])
  const { data: apps } = useApi(listApps)
  const { data: runs, refetch: refetchRuns } = useApi(
    () => listRuns(packId, 20), [packId]
  )

  if (loading) return <Screen title="Pack Detail"><LoadingSpinner /></Screen>
  if (error || !pack) return <Screen title="Pack Detail"><ErrorBanner message={error || 'Pack not found'} /></Screen>

  const handleDelete = async () => {
    if (!confirm(`Delete "${pack.name}"?`)) return
    await deletePack(pack.id).catch(() => {})
    nav('/packs')
  }

  return (
    <Screen
      title={pack.name}
      crumbs={['Validation Packs', pack.name]}
      sub={pack.description || undefined}
      right={
        <Row gap={8}>
          <Button variant="primary" icon="▸" onClick={() => setShowRun(true)}>Run pack</Button>
          <Button variant="danger" onClick={handleDelete}>Delete</Button>
        </Row>
      }
    >
      {showRun && (
        <RunModal
          packId={pack.id}
          apps={apps || []}
          onClose={() => setShowRun(false)}
          onStarted={runId => { refetchRuns(); nav(`/runs/${runId}`) }}
        />
      )}

      <Row gap={20} style={{ alignItems: 'flex-start' }}>
        {/* Steps list */}
        <Col gap={16} style={{ flex: 2 }}>
          <Card pad={0}>
            <Row style={{ padding: '14px 20px', justifyContent: 'space-between', alignItems: 'center', borderBottom: `1px solid ${P.border}` }}>
              <div>
                <Eyebrow>Validation steps</Eyebrow>
                <Text size={13} weight={500} style={{ marginTop: 2 }}>{pack.steps.length} step{pack.steps.length !== 1 ? 's' : ''}</Text>
              </div>
              <Meter value={Math.min(100, pack.steps.length * 10)} color={P.accent} height={4} style={{ width: 80 }} />
            </Row>
            {pack.steps.length === 0 ? (
              <div style={{ padding: 32, textAlign: 'center' }}>
                <Text size={13} color={P.textMute}>No steps defined. Edit this pack to add steps.</Text>
              </div>
            ) : (
              pack.steps.map((step, i) => <StepRow key={step.step_id} step={step} idx={i} />)
            )}
          </Card>
        </Col>

        {/* Sidebar: meta + recent runs */}
        <Col gap={16} style={{ width: 280, flexShrink: 0 }}>
          {/* Meta */}
          <Card>
            <Eyebrow style={{ marginBottom: 10 }}>Details</Eyebrow>
            <Col gap={8}>
              <Row style={{ justifyContent: 'space-between' }}>
                <Text size={12} color={P.textDim}>Pack ID</Text>
                <Text size={11} mono color={P.textMute}>{pack.id.slice(0, 8)}</Text>
              </Row>
              <Row style={{ justifyContent: 'space-between' }}>
                <Text size={12} color={P.textDim}>Steps</Text>
                <Text size={12} mono>{pack.steps.length}</Text>
              </Row>
              <Row style={{ justifyContent: 'space-between' }}>
                <Text size={12} color={P.textDim}>Created</Text>
                <Text size={11} mono color={P.textMute}>{new Date(pack.created_at).toLocaleDateString()}</Text>
              </Row>
              <Row style={{ justifyContent: 'space-between' }}>
                <Text size={12} color={P.textDim}>Updated</Text>
                <Text size={11} mono color={P.textMute}>{new Date(pack.updated_at).toLocaleDateString()}</Text>
              </Row>
            </Col>
          </Card>

          {/* Recent runs */}
          <Card pad={0}>
            <Row style={{ padding: '12px 16px', justifyContent: 'space-between', alignItems: 'center', borderBottom: `1px solid ${P.border}` }}>
              <Eyebrow>Recent runs</Eyebrow>
              <Button size="sm" variant="ghost" onClick={() => nav(`/runs?pack_id=${pack.id}`)}>All →</Button>
            </Row>
            {!runs?.length ? (
              <div style={{ padding: '20px 16px' }}>
                <Text size={12} color={P.textMute}>No runs yet.</Text>
              </div>
            ) : (
              runs.slice(0, 6).map((run, i) => {
                const status = run.status as string
                const kind = status === 'completed' ? 'pass' : status === 'failed' ? 'fail' : status === 'running' ? 'running' : 'unclear'
                return (
                  <Row key={run.id} style={{
                    padding: '10px 16px', alignItems: 'center', gap: 10,
                    borderBottom: i < Math.min(runs.length, 6) - 1 ? `1px solid ${P.border}` : 'none',
                    cursor: 'pointer',
                  }} onClick={() => nav(`/runs/${run.id}`)}>
                    <Pill kind={kind as any} small style={{ width: 70, justifyContent: 'center' }} />
                    <Text size={11} color={P.textMute} mono style={{ flex: 1 }}>
                      {run.id.slice(0, 8)}
                    </Text>
                    <Text size={10} color={P.textMute} mono>
                      {run.created_at ? new Date(run.created_at).toLocaleDateString() : '—'}
                    </Text>
                  </Row>
                )
              })
            )}
          </Card>
        </Col>
      </Row>
    </Screen>
  )
}
