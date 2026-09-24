import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { listRuns, cancelRun } from '../api/client'
import { useApi } from '../hooks/useApi'
import {
  Screen, Card, Row, Col, Display, Text, Eyebrow, Pill, Button,
  Meter, LoadingSpinner, ErrorBanner, EmptyState,
} from '../design/components'
import { P, F } from '../design/tokens'

const STATUS_KINDS: Record<string, string> = {
  completed: 'pass',
  failed: 'fail',
  running: 'running',
  cancelled: 'blocked',
  pending: 'unclear',
}

export default function Runs() {
  const nav = useNavigate()
  const [params] = useSearchParams()
  const filterPackId = params.get('pack_id') ?? undefined
  const [limit] = useState(50)

  const { data: runs, loading, error, refetch } = useApi(
    () => listRuns(filterPackId, limit), [filterPackId ?? '', limit]
  )

  const handleCancel = async (id: string) => {
    if (!confirm('Cancel this run?')) return
    await cancelRun(id).catch(() => {})
    refetch()
  }

  const running = runs?.filter(r => r.status === 'running') ?? []
  const rest = runs?.filter(r => r.status !== 'running') ?? []

  return (
    <Screen
      title="Live Test Runs"
      sub={runs ? `${runs.length} run${runs.length !== 1 ? 's' : ''}${filterPackId ? ' for this pack' : ' across all packs'}` : undefined}
      right={
        <Row gap={8}>
          <Button variant="ghost" onClick={refetch}>↻</Button>
          <Button variant="primary" icon="▸" onClick={() => nav('/packs')}>Start new run</Button>
        </Row>
      }
    >
      {loading ? <LoadingSpinner /> : error ? <ErrorBanner message={error} /> : !runs?.length ? (
        <EmptyState
          message="No runs yet. Start a run from a validation pack."
          action={<Button variant="primary" icon="▸" onClick={() => nav('/packs')}>Go to packs →</Button>}
        />
      ) : (
        <Col gap={16}>
          {/* Active runs */}
          {running.length > 0 && (
            <div>
              <Eyebrow style={{ marginBottom: 10 }}>Active</Eyebrow>
              <Col gap={8}>
                {running.map(run => {
                  const passed = run.step_results.filter(s => s.status === 'passed' || s.status === 'dry_run_only').length
                  const total = run.step_results.length
                  const progress = total > 0 ? Math.round((passed / total) * 100) : 0
                  return (
                    <Card key={run.id} elevated style={{ borderLeft: `3px solid ${P.accent}` }}>
                      <Row style={{ alignItems: 'center', gap: 14 }}>
                        <div style={{
                          width: 38, height: 38, borderRadius: 10,
                          background: `${P.accent}22`, border: `1px solid ${P.accent}44`,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontFamily: F.mono, fontSize: 11, color: P.accent, flexShrink: 0,
                        }}>{run.pack_id.slice(0, 2).toUpperCase()}</div>
                        <Col gap={3} style={{ flex: 1 }}>
                          <Text size={13} weight={500}>Run {run.id.slice(0, 8)}</Text>
                          <Text size={11} color={P.textMute} mono>Pack {run.pack_id.slice(0, 8)}</Text>
                        </Col>
                        <Col gap={4} style={{ width: 140 }}>
                          <Meter value={progress} color={P.accent} height={4} animated />
                          <Text size={10} color={P.textMute} mono>{passed}/{total} steps</Text>
                        </Col>
                        <Pill kind="running" glow small />
                        <Row gap={6}>
                          <Button size="sm" variant="primary" onClick={() => nav(`/runs/${run.id}`)}>Watch</Button>
                          <Button size="sm" variant="danger" onClick={() => handleCancel(run.id)}>Cancel</Button>
                        </Row>
                      </Row>
                    </Card>
                  )
                })}
              </Col>
            </div>
          )}

          {/* History */}
          {rest.length > 0 && (
            <div>
              {running.length > 0 && <Eyebrow style={{ marginBottom: 10 }}>History</Eyebrow>}
              <Card pad={0}>
                {/* Header */}
                <div style={{
                  display: 'grid', gridTemplateColumns: '36px 2fr 1fr 120px 100px 110px 90px',
                  padding: '10px 20px', borderBottom: `1px solid ${P.border}`,
                }}>
                  {['', 'Run', 'Pack', 'Steps', 'Status', 'Started', ''].map((h, i) => (
                    <Eyebrow key={i}>{h}</Eyebrow>
                  ))}
                </div>

                {rest.map((run, idx) => {
                  const passed = run.step_results.filter(s => s.status === 'passed' || s.status === 'dry_run_only').length
                  const total = run.step_results.length
                  const progress = total > 0 ? Math.round((passed / total) * 100) : 0
                  const kind = STATUS_KINDS[run.status] || 'unclear'
                  return (
                    <div
                      key={run.id}
                      onClick={() => nav(`/runs/${run.id}`)}
                      style={{
                        display: 'grid', gridTemplateColumns: '36px 2fr 1fr 120px 100px 110px 90px',
                        padding: '12px 20px', alignItems: 'center',
                        borderBottom: idx < rest.length - 1 ? `1px solid ${P.border}` : 'none',
                        cursor: 'pointer',
                      }}
                      onMouseEnter={e => (e.currentTarget.style.background = P.cardHi)}
                      onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                    >
                      {/* Icon */}
                      <div style={{
                        width: 28, height: 28, borderRadius: 8,
                        background: P.cardHi, border: `1px solid ${P.border}`,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontFamily: F.mono, fontSize: 10, color: P.textMute,
                      }}>{run.pack_id.slice(0, 2).toUpperCase()}</div>

                      {/* Run ID */}
                      <Col gap={1}>
                        <Text size={13} weight={500} mono>Run {run.id.slice(0, 8)}</Text>
                        {run.error && <Text size={11} color={P.fail}>{run.error.slice(0, 40)}</Text>}
                      </Col>

                      {/* Pack */}
                      <Text size={12} color={P.textDim} mono>{run.pack_id.slice(0, 8)}</Text>

                      {/* Steps meter */}
                      <div style={{ paddingRight: 12 }}>
                        <Meter value={progress} color={kind === 'pass' ? P.pass : kind === 'fail' ? P.fail : P.unclear} height={4} />
                        <Text size={10} color={P.textMute} mono style={{ marginTop: 3 }}>{passed}/{total}</Text>
                      </div>

                      {/* Status */}
                      <Pill kind={kind as any} small />

                      {/* Started */}
                      <Text size={11} color={P.textMute} mono>
                        {run.created_at ? new Date(run.created_at).toLocaleString() : '—'}
                      </Text>

                      {/* Actions */}
                      <div onClick={e => e.stopPropagation()}>
                        <Button size="sm" onClick={() => nav(`/runs/${run.id}`)}>Open</Button>
                      </div>
                    </div>
                  )
                })}
              </Card>
            </div>
          )}
        </Col>
      )}
    </Screen>
  )
}
