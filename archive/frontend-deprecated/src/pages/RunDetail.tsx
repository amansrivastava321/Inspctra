import { useParams, useNavigate } from 'react-router-dom'
import { getRun, cancelRun } from '../api/client'
import { useApi } from '../hooks/useApi'
import { useSSE } from '../hooks/useSSE'
import {
  Screen, Card, Row, Col, Display, Text, Eyebrow, Pill, Button,
  StatusDot, Meter, LoadingSpinner, ErrorBanner,
} from '../design/components'
import { P, F } from '../design/tokens'
import type { SSEStepResultEvent, SSEStepStartEvent, SSEStatusEvent } from '../api/types'

const STATUS_KIND: Record<string, string> = {
  completed: 'pass', failed: 'fail', running: 'running',
  cancelled: 'blocked', pending: 'unclear',
}

const STEP_STATUS_KIND: Record<string, string> = {
  passed: 'pass', failed: 'fail', dry_run_only: 'pass',
  running: 'running', pending: 'unclear', skipped: 'blocked',
}

function EventLog({ events }: { events: { type: string; data: unknown; receivedAt: string }[] }) {
  return (
    <div style={{
      flex: 1, overflowY: 'auto', padding: '12px 16px',
      fontFamily: F.mono, fontSize: 11, lineHeight: 1.6,
      background: '#080b12', borderRadius: 10,
      border: `1px solid ${P.border}`,
      maxHeight: 320,
    }}>
      {events.length === 0 && (
        <Text size={11} color={P.textMute}>Waiting for events…</Text>
      )}
      {events.map((e, i) => {
        const ts = new Date(e.receivedAt).toLocaleTimeString()
        const dataStr = typeof e.data === 'object' ? JSON.stringify(e.data) : String(e.data)
        const color = e.type === 'done' ? P.pass : e.type === 'error' ? P.fail : e.type === 'step_result' ? P.accent : P.textDim
        return (
          <div key={i} style={{ marginBottom: 3 }}>
            <span style={{ color: P.textMute }}>{ts} </span>
            <span style={{ color }}>{e.type}</span>
            <span style={{ color: P.textDim }}> {dataStr}</span>
          </div>
        )
      })}
    </div>
  )
}

export default function RunDetail() {
  const { runId } = useParams<{ runId: string }>()
  const nav = useNavigate()

  const { data: run, loading, error, refetch } = useApi(() => getRun(runId!), [runId])
  const { events, connected, done } = useSSE(run?.status === 'running' || run?.status === 'pending' ? runId ?? null : null)

  // Derive latest step states from SSE + fallback to run.step_results
  const stepResultsFromSSE: Record<number, SSEStepResultEvent> = {}
  let currentStep: SSEStepStartEvent | null = null
  let latestStatus: string | null = null

  for (const ev of events) {
    if (ev.type === 'step_result') {
      const d = ev.data as SSEStepResultEvent
      stepResultsFromSSE[d.step] = d
    }
    if (ev.type === 'step_start') {
      currentStep = ev.data as SSEStepStartEvent
    }
    if (ev.type === 'status') {
      latestStatus = (ev.data as SSEStatusEvent).status
    }
  }

  const activeStatus = latestStatus || run?.status || 'pending'
  const kind = STATUS_KIND[activeStatus] || 'unclear'

  const passed = run?.step_results.filter(s => s.status === 'passed' || s.status === 'dry_run_only').length ?? 0
  const total = run?.step_results.length ?? 0

  // Live progress from SSE
  const ssePassedCount = Object.values(stepResultsFromSSE).filter(
    s => s.status === 'passed' || s.status === 'dry_run_only'
  ).length
  const sseTotal = currentStep?.total ?? total
  const liveProgress = sseTotal > 0
    ? Math.round((ssePassedCount / sseTotal) * 100)
    : total > 0 ? Math.round((passed / total) * 100) : 0

  const handleCancel = async () => {
    if (!run || !confirm('Cancel this run?')) return
    await cancelRun(run.id).catch(() => {})
    refetch()
  }

  if (loading) return <Screen title="Run Detail"><LoadingSpinner /></Screen>
  if (error || !run) return <Screen title="Run Detail"><ErrorBanner message={error || 'Run not found'} /></Screen>

  return (
    <Screen
      title={`Run ${run.id.slice(0, 8)}`}
      crumbs={['Runs', run.id.slice(0, 8)]}
      sub={`Pack ${run.pack_id.slice(0, 8)}`}
      right={
        <Row gap={8}>
          <Button variant="ghost" onClick={refetch}>↻</Button>
          {run.status === 'running' && (
            <Button variant="danger" onClick={handleCancel}>Cancel run</Button>
          )}
          <Button variant="ghost" onClick={() => nav('/runs')}>← All runs</Button>
        </Row>
      }
    >
      <Col gap={20}>
        {/* Hero status bar */}
        <Card glow={kind === 'pass'} style={{ position: 'relative', overflow: 'hidden' }}>
          <div style={{
            position: 'absolute', inset: 0, pointerEvents: 'none',
            background: `radial-gradient(50% 70% at 80% 20%, ${P[kind as keyof typeof P] || P.accent}18, transparent 55%)`,
          }} />
          <Row gap={28} style={{ position: 'relative', alignItems: 'center' }}>
            <StatusDot kind={kind as any} size={56} glow={kind === 'running'} />
            <Col gap={6} style={{ flex: 1 }}>
              <Row gap={10} style={{ alignItems: 'center' }}>
                <Pill kind={kind as any} glow={kind === 'running'} />
                {connected && (
                  <span style={{
                    display: 'inline-flex', alignItems: 'center', gap: 6,
                    padding: '2px 10px', borderRadius: 99,
                    fontFamily: F.mono, fontSize: 10,
                    background: `${P.pass}18`, border: `1px solid ${P.pass}33`, color: P.pass,
                  }}>
                    <span style={{ width: 5, height: 5, borderRadius: 99, background: P.pass, animation: 'pulse 1.2s ease-in-out infinite' }} />
                    LIVE
                  </span>
                )}
              </Row>
              <Display size={14} weight={500} color={P.textDim} style={{ letterSpacing: 0 }}>
                {currentStep ? `Step ${currentStep.step}/${currentStep.total}: ${currentStep.description}` : `${passed}/${total} steps completed`}
              </Display>
              <Meter value={liveProgress} color={kind === 'pass' ? P.pass : kind === 'fail' ? P.fail : P.accent} height={6} animated={kind === 'running'} />
            </Col>
            <Col gap={4} style={{ flexShrink: 0 }}>
              <Row gap={16}>
                <Col gap={2}>
                  <Eyebrow>Started</Eyebrow>
                  <Text size={12} mono>{run.started_at ? new Date(run.started_at).toLocaleTimeString() : '—'}</Text>
                </Col>
                <Col gap={2}>
                  <Eyebrow>Completed</Eyebrow>
                  <Text size={12} mono>{run.completed_at ? new Date(run.completed_at).toLocaleTimeString() : '—'}</Text>
                </Col>
              </Row>
            </Col>
          </Row>
          <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }`}</style>
        </Card>

        <Row gap={20} style={{ alignItems: 'flex-start' }}>
          {/* Step results */}
          <Col gap={0} style={{ flex: 2 }}>
            <Card pad={0}>
              <div style={{ padding: '14px 20px', borderBottom: `1px solid ${P.border}` }}>
                <Eyebrow>Step results</Eyebrow>
              </div>
              {run.step_results.length === 0 && events.length === 0 ? (
                <div style={{ padding: 32, textAlign: 'center' }}>
                  <Text size={13} color={P.textMute}>
                    {run.status === 'pending' ? 'Run queued, waiting to start…' : 'No step results yet.'}
                  </Text>
                </div>
              ) : (
                run.step_results.map((step, i) => {
                  // Overlay with SSE data if available
                  const live = stepResultsFromSSE[step.step]
                  const status = live?.status ?? step.status
                  const notes = live?.notes ?? step.notes ?? ''
                  const sk = STEP_STATUS_KIND[status] || 'unclear'
                  const isCurrent = currentStep?.step === step.step && run.status === 'running'
                  return (
                    <Row key={i} style={{
                      padding: '12px 20px', gap: 14, alignItems: 'flex-start',
                      borderBottom: i < run.step_results.length - 1 ? `1px solid ${P.border}` : 'none',
                      background: isCurrent ? `${P.accent}08` : 'transparent',
                    }}>
                      <StatusDot kind={sk as any} size={22} glow={isCurrent} />
                      <Col gap={3} style={{ flex: 1 }}>
                        <Row gap={8} style={{ alignItems: 'center' }}>
                          <Text size={12} mono color={P.textMute}>Step {step.step}</Text>
                          {step.action_type && (
                            <span style={{
                              padding: '1px 7px', borderRadius: 99,
                              fontFamily: F.mono, fontSize: 9.5,
                              background: P.cardHi, border: `1px solid ${P.border}`,
                              color: P.textDim,
                            }}>{step.action_type}</span>
                          )}
                          {isCurrent && <span style={{ color: P.accent, fontSize: 11, fontFamily: F.mono }}>● running</span>}
                        </Row>
                        {notes && <Text size={12} color={P.textDim}>{notes}</Text>}
                        {step.mode === 'dry_run' && (
                          <Text size={11} color={P.textMute} mono>dry-run mode</Text>
                        )}
                      </Col>
                      <Pill kind={sk as any} small />
                    </Row>
                  )
                })
              )}
            </Card>
          </Col>

          {/* Right sidebar */}
          <Col gap={16} style={{ width: 280, flexShrink: 0 }}>
            {/* Run meta */}
            <Card>
              <Eyebrow style={{ marginBottom: 10 }}>Run info</Eyebrow>
              <Col gap={8}>
                <Row style={{ justifyContent: 'space-between' }}>
                  <Text size={12} color={P.textDim}>Run ID</Text>
                  <Text size={11} mono color={P.textMute}>{run.id.slice(0, 12)}</Text>
                </Row>
                <Row style={{ justifyContent: 'space-between' }}>
                  <Text size={12} color={P.textDim}>Pack</Text>
                  <Text size={11} mono color={P.textMute}>{run.pack_id.slice(0, 8)}</Text>
                </Row>
                <Row style={{ justifyContent: 'space-between' }}>
                  <Text size={12} color={P.textDim}>App target</Text>
                  <Text size={11} mono color={P.textMute}>{run.app_target_id.slice(0, 8)}</Text>
                </Row>
                <Row style={{ justifyContent: 'space-between' }}>
                  <Text size={12} color={P.textDim}>Steps passed</Text>
                  <Text size={12} mono>{passed}/{total}</Text>
                </Row>
                {run.error && (
                  <div style={{ padding: '8px 10px', borderRadius: 8, background: `${P.fail}11`, border: `1px solid ${P.fail}33` }}>
                    <Text size={11} color={P.fail}>{run.error}</Text>
                  </div>
                )}
              </Col>
            </Card>

            {/* Event log */}
            <Card pad={14}>
              <Row style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <Eyebrow>Event stream</Eyebrow>
                {done && <Text size={10} color={P.pass} mono>DONE</Text>}
                {connected && <Text size={10} color={P.pass} mono>LIVE</Text>}
              </Row>
              <EventLog events={events} />
            </Card>
          </Col>
        </Row>
      </Col>
    </Screen>
  )
}
