import { useNavigate } from 'react-router-dom'
import { getDashboard } from '../api/client'
import { useApi } from '../hooks/useApi'
import {
  Screen, Card, Row, Col, Display, Text, Eyebrow, Pill, Button,
  Meter, LoadingSpinner, ErrorBanner,
} from '../design/components'
import { P, F } from '../design/tokens'
import type { LiveRunRecord } from '../api/types'

function RunRow({ run, idx }: { run: LiveRunRecord; idx: number }) {
  const nav = useNavigate()
  const status = run.status as 'pass' | 'fail' | 'unclear' | 'blocked' | 'running' | 'pending' | 'completed' | 'failed' | 'cancelled'
  const verdictKind = status === 'completed' ? 'pass' : status === 'failed' ? 'fail' : status as string

  const passedSteps = run.step_results.filter(s => s.status === 'passed' || s.status === 'dry_run_only').length
  const totalSteps  = run.step_results.length
  const conf        = totalSteps > 0 ? Math.round((passedSteps / totalSteps) * 100) : 0

  return (
    <Row style={{
      padding: '14px 20px', alignItems: 'center', gap: 14,
      borderBottom: idx < 4 ? `1px solid ${P.border}` : 'none',
    }}>
      <div style={{
        width: 36, height: 36, borderRadius: 9,
        background: P.cardHi, border: `1px solid ${P.border}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: F.mono, fontSize: 11, color: P.textDim, flexShrink: 0,
      }}>
        {run.pack_id.slice(0, 2).toUpperCase()}
      </div>
      <Col gap={2} style={{ minWidth: 180, flex: 1 }}>
        <Text size={13} weight={500}>Run {run.id.slice(0, 8)}</Text>
        <Text size={11} color={P.textMute} mono>Pack {run.pack_id.slice(0, 8)} · {run.status}</Text>
      </Col>
      <div style={{ flex: 1, maxWidth: 200 }}>
        {conf > 0 && <Meter value={conf} color={verdictKind === 'pass' ? P.pass : verdictKind === 'fail' ? P.fail : P.unclear} label="steps" />}
        {conf === 0 && <Text size={11} color={P.textMute}>—</Text>}
      </div>
      <Pill kind={verdictKind as any} small style={{ width: 100, justifyContent: 'center' }} />
      <Text size={11} color={P.textMute} mono style={{ width: 90, textAlign: 'right' }}>
        {run.created_at ? new Date(run.created_at).toLocaleTimeString() : '—'}
      </Text>
      <Button size="sm" onClick={() => nav(`/runs/${run.id}`)}>Open</Button>
    </Row>
  )
}

export default function Dashboard() {
  const { data, loading, error, refetch } = useApi(getDashboard)
  const nav = useNavigate()

  const score = 84 // static until we wire doctor endpoint

  return (
    <Screen
      title="Workspace"
      crumbs={['local workspace']}
      readinessScore={score}
      right={
        <Row gap={8}>
          <Button variant="ghost" onClick={refetch}>↻</Button>
          <Button variant="primary" icon="▸" onClick={() => nav('/packs')}>Start live test</Button>
        </Row>
      }
    >
      <Col gap={20} style={{ height: '100%', overflowY: 'auto' }}>
        {/* Hero */}
        <Card glow pad={28} style={{ position: 'relative', overflow: 'hidden' }}>
          <div style={{
            position: 'absolute', inset: 0, pointerEvents: 'none',
            background: `radial-gradient(60% 80% at 80% 20%, rgba(91,140,255,0.10), transparent 55%),
                         radial-gradient(50% 70% at 20% 90%, rgba(52,211,153,0.06), transparent 60%)`,
          }} />
          <Row gap={32} style={{ position: 'relative', alignItems: 'stretch' }}>
            <Col gap={16} style={{ width: 320, flexShrink: 0 }}>
              <Row gap={8} style={{ alignItems: 'center' }}>
                <Eyebrow color={P.accent}>Workspace health</Eyebrow>
              </Row>
              <Display size={22} weight={500} style={{ color: P.textDim }}>
                Is my software healthy?
              </Display>
              <Row gap={20} style={{ alignItems: 'flex-end', marginTop: 8 }}>
                <Display size={88} weight={600} style={{
                  background: `linear-gradient(180deg, ${P.text}, #b0b3bd)`,
                  WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
                  letterSpacing: -3,
                }}>{score}</Display>
                <Col gap={2} style={{ marginBottom: 14 }}>
                  <Text size={14} color={P.textDim}>/ 100</Text>
                  <Pill kind="ready" small>USABLE</Pill>
                </Col>
              </Row>
              <Row gap={8} style={{ marginTop: 4 }}>
                <Button variant="primary" size="lg" icon="▸" onClick={() => nav('/packs')}>Start live test</Button>
                <Button variant="ghost" size="lg" onClick={() => nav('/doctor')}>Runtime Doctor</Button>
              </Row>
            </Col>
            <div style={{ width: 1, background: P.border, flexShrink: 0 }} />
            <Col gap={10} style={{ flex: 1 }}>
              <Eyebrow>Quick stats</Eyebrow>
              {loading ? <LoadingSpinner /> : error ? <ErrorBanner message={error} /> : (
                <Col gap={8}>
                  <Row style={{ justifyContent: 'space-between' }}>
                    <Text size={13} color={P.textDim}>Projects</Text>
                    <Text size={13} mono>{data?.project_count ?? 0}</Text>
                  </Row>
                  <Row style={{ justifyContent: 'space-between' }}>
                    <Text size={13} color={P.textDim}>App targets</Text>
                    <Text size={13} mono>{data?.app_target_count ?? 0}</Text>
                  </Row>
                  <Row style={{ justifyContent: 'space-between' }}>
                    <Text size={13} color={P.textDim}>Validation packs</Text>
                    <Text size={13} mono>{data?.validation_pack_count ?? 0}</Text>
                  </Row>
                  <Row style={{ justifyContent: 'space-between' }}>
                    <Text size={13} color={P.textDim}>Total runs</Text>
                    <Text size={13} mono>{data?.total_runs ?? 0}</Text>
                  </Row>
                </Col>
              )}
            </Col>
          </Row>
        </Card>

        {/* KPI row */}
        {!loading && !error && data && (
          <Row gap={16}>
            {[
              { label: 'Total runs',     value: String(data.total_runs),     sub: 'all time',             kind: null },
              { label: 'Completed',      value: String(data.runs_completed), sub: 'successful',           kind: 'pass' },
              { label: 'Failed',         value: String(data.runs_failed),    sub: 'need attention',       kind: data.runs_failed > 0 ? 'fail' : null },
              { label: 'Running now',    value: String(data.runs_running),   sub: 'active runs',          kind: data.runs_running > 0 ? 'running' : null },
              { label: 'App targets',    value: String(data.app_target_count), sub: 'connected apps',     kind: null },
            ].map((k, i) => (
              <Card key={i} pad={16} style={{ flex: 1, minWidth: 0 }}>
                <Eyebrow>{k.label}</Eyebrow>
                <Row gap={8} style={{ alignItems: 'baseline', marginTop: 6 }}>
                  <Display size={24}>{k.value}</Display>
                  {k.kind && <span style={{ width: 6, height: 6, borderRadius: 99, background: P[k.kind as keyof typeof P] as string }} />}
                </Row>
                <Text size={11.5} color={P.textMute} style={{ marginTop: 6 }}>{k.sub}</Text>
              </Card>
            ))}
          </Row>
        )}

        {/* Recent runs */}
        <Card style={{ flex: 1 }} pad={0}>
          <Row style={{ padding: '16px 20px', alignItems: 'center', justifyContent: 'space-between', borderBottom: `1px solid ${P.border}` }}>
            <div>
              <Eyebrow>Latest runs</Eyebrow>
              <Text size={14} weight={500} style={{ marginTop: 2 }}>Across all packs</Text>
            </div>
            <Button variant="ghost" size="sm" onClick={() => nav('/runs')}>View all →</Button>
          </Row>
          {loading ? (
            <LoadingSpinner />
          ) : error ? (
            <div style={{ padding: 20 }}><ErrorBanner message={error} /></div>
          ) : data?.recent_runs && data.recent_runs.length > 0 ? (
            <Col gap={0}>
              {data.recent_runs.slice(0, 5).map((run, i) => (
                <RunRow key={run.id} run={run} idx={i} />
              ))}
            </Col>
          ) : (
            <div style={{ padding: 32, textAlign: 'center' }}>
              <Text size={13} color={P.textMute}>No runs yet. Start one from a validation pack.</Text>
              <div style={{ marginTop: 12 }}>
                <Button variant="primary" onClick={() => nav('/packs')}>Go to packs →</Button>
              </div>
            </div>
          )}
        </Card>
      </Col>
    </Screen>
  )
}
