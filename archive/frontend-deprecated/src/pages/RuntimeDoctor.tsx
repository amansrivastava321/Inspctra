import { useState } from 'react'
import { getRuntimeDoctor } from '../api/client'
import { useApi } from '../hooks/useApi'
import {
  Screen, Card, Row, Col, Display, Text, Eyebrow, Pill, Button,
  Meter, LoadingSpinner, ErrorBanner,
} from '../design/components'
import { P, F } from '../design/tokens'
import type { DriverReadiness } from '../api/types'

const APP_TYPE_FILTERS = ['web', 'android', 'ios', 'native_macos', 'native_windows', 'backend_fastapi', 'backend_node']

function StatusRow({ label, ok, detail }: { label: string; ok: boolean | undefined; detail?: string }) {
  if (ok === undefined) return null
  return (
    <Row style={{ padding: '10px 0', borderBottom: `1px solid ${P.border}`, alignItems: 'center', gap: 12 }}>
      <div style={{
        width: 20, height: 20, borderRadius: 99,
        background: ok ? `${P.pass}22` : `${P.fail}22`,
        border: `1px solid ${ok ? P.pass : P.fail}55`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: ok ? P.pass : P.fail, fontSize: 10, flexShrink: 0,
      }}>{ok ? '✓' : '✕'}</div>
      <Col gap={1} style={{ flex: 1 }}>
        <Text size={13}>{label}</Text>
        {detail && <Text size={11} color={P.textMute}>{detail}</Text>}
      </Col>
      <Pill kind={ok ? 'pass' : 'fail'} small />
    </Row>
  )
}

function DriverCard({ dr }: { dr: DriverReadiness }) {
  const [expanded, setExpanded] = useState(false)
  const ok = dr.status === 'ready'
  return (
    <Card style={{ borderLeft: `3px solid ${ok ? P.pass : P.fail}` }}>
      <Row style={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <Row gap={10} style={{ alignItems: 'center' }}>
          <Pill kind={ok ? 'pass' : 'fail'} small />
          <div>
            <Text size={13} weight={500}>{dr.app_type}</Text>
            <Text size={11} color={P.textMute} mono>{dr.driver_type}</Text>
          </div>
        </Row>
        {(!ok && dr.missing_deps.length > 0) && (
          <Button variant="ghost" size="sm" onClick={() => setExpanded(v => !v)}>
            {expanded ? 'Hide' : `${dr.missing_deps.length} missing`}
          </Button>
        )}
      </Row>
      {expanded && (
        <Col gap={8} style={{ marginTop: 12 }}>
          {dr.missing_deps.length > 0 && (
            <Col gap={4}>
              <Eyebrow>Missing dependencies</Eyebrow>
              {dr.missing_deps.map((d, i) => (
                <Text key={i} size={12} color={P.fail} mono style={{ padding: '3px 8px', background: `${P.fail}11`, borderRadius: 6 }}>{d}</Text>
              ))}
            </Col>
          )}
          {dr.setup_instructions.length > 0 && (
            <Col gap={4}>
              <Eyebrow>Setup</Eyebrow>
              {dr.setup_instructions.map((s, i) => (
                <Text key={i} size={12} color={P.textDim} style={{ paddingLeft: 8 }}>→ {s}</Text>
              ))}
            </Col>
          )}
        </Col>
      )}
    </Card>
  )
}

export default function RuntimeDoctor() {
  const [selected, setSelected] = useState<string[]>([])
  const { data, loading, error, refetch } = useApi(
    () => getRuntimeDoctor(selected.length > 0 ? selected : undefined),
    [selected.join(',')]
  )

  const score = data?.readiness_score ?? 0
  const scoreColor = score >= 80 ? P.pass : score >= 50 ? P.unclear : P.fail

  const toggleFilter = (t: string) =>
    setSelected(prev => prev.includes(t) ? prev.filter(x => x !== t) : [...prev, t])

  return (
    <Screen
      title="Runtime Doctor"
      sub="Check environment readiness for test execution"
      right={
        <Row gap={8}>
          <Button variant="ghost" onClick={refetch}>↻ Re-scan</Button>
        </Row>
      }
    >
      <Col gap={20}>
        {/* Filter bar */}
        <Row gap={8} style={{ flexWrap: 'wrap' }}>
          <Text size={12} color={P.textMute} style={{ alignSelf: 'center' }}>Filter:</Text>
          {APP_TYPE_FILTERS.map(t => (
            <button key={t} onClick={() => toggleFilter(t)} style={{
              padding: '4px 12px', borderRadius: 99,
              fontFamily: F.mono, fontSize: 11,
              background: selected.includes(t) ? `${P.accent}22` : P.cardHi,
              border: `1px solid ${selected.includes(t) ? P.accent : P.border}`,
              color: selected.includes(t) ? P.accent : P.textDim,
              cursor: 'pointer',
            }}>{t}</button>
          ))}
        </Row>

        {loading ? <LoadingSpinner /> : error ? <ErrorBanner message={error} /> : data && (
          <>
            {/* Score hero */}
            <Card glow={score >= 80} style={{ position: 'relative', overflow: 'hidden' }}>
              <div style={{
                position: 'absolute', inset: 0, pointerEvents: 'none',
                background: `radial-gradient(60% 80% at 80% 20%, ${scoreColor}18, transparent 55%)`,
              }} />
              <Row gap={40} style={{ position: 'relative', alignItems: 'center' }}>
                <Col gap={8}>
                  <Eyebrow>Readiness score</Eyebrow>
                  <Row gap={16} style={{ alignItems: 'flex-end' }}>
                    <Display size={72} weight={700} style={{
                      background: `linear-gradient(180deg, ${scoreColor}, ${scoreColor}99)`,
                      WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
                      letterSpacing: -2,
                    }}>{score}</Display>
                    <Col gap={4} style={{ marginBottom: 10 }}>
                      <Text size={13} color={P.textDim}>/ 100</Text>
                      <Pill kind={score >= 80 ? 'pass' : score >= 50 ? 'unclear' : 'fail'} small>
                        {data.readiness_label ?? (score >= 80 ? 'READY' : score >= 50 ? 'PARTIAL' : 'NOT READY')}
                      </Pill>
                    </Col>
                  </Row>
                  <Meter value={score} color={scoreColor} height={6} animated />
                </Col>
                <Col gap={4} style={{ flex: 1 }}>
                  <Text size={12} color={P.textDim}>Platform: <span style={{ fontFamily: F.mono, color: P.text }}>{data.platform ?? '—'}</span></Text>
                  <Text size={12} color={P.textDim}>Python: <span style={{ fontFamily: F.mono, color: P.text }}>{data.python_version ?? '—'}</span></Text>
                  {data.ollama_configured_model && (
                    <Text size={12} color={P.textDim}>LLM model: <span style={{ fontFamily: F.mono, color: P.text }}>{data.ollama_configured_model}</span></Text>
                  )}
                  {data.appium_server_url && (
                    <Text size={12} color={P.textDim}>Appium: <span style={{ fontFamily: F.mono, color: P.text }}>{data.appium_server_url}</span></Text>
                  )}
                </Col>
              </Row>
            </Card>

            <Row gap={20} style={{ alignItems: 'flex-start' }}>
              {/* Component checks */}
              <Col gap={0} style={{ flex: 1 }}>
                <Card pad={0}>
                  <div style={{ padding: '14px 20px', borderBottom: `1px solid ${P.border}` }}>
                    <Eyebrow>Component checks</Eyebrow>
                  </div>
                  <div style={{ padding: '0 20px' }}>
                    <StatusRow label="Playwright installed" ok={data.playwright_installed} />
                    <StatusRow label="Playwright browsers" ok={data.playwright_browsers_installed} />
                    <StatusRow label="Appium client" ok={data.appium_client_installed} />
                    <StatusRow label="npm available" ok={data.npm_available} />
                    <StatusRow label="Appium CLI" ok={data.appium_command_available} />
                    <StatusRow label="Appium UiAutomator2" ok={data.appium_uiautomator2_installed} />
                    <StatusRow label="Appium XCUITest" ok={data.appium_xcuitest_installed} />
                    <StatusRow label="Ollama reachable" ok={data.ollama_reachable}
                      detail={data.ollama_models?.length ? `Models: ${data.ollama_models.slice(0, 3).join(', ')}` : undefined} />
                    <StatusRow label="Vision model available" ok={data.ollama_vision_model_available} />
                    <StatusRow label="Appium server reachable" ok={data.appium_server_reachable} />
                  </div>
                </Card>
              </Col>

              {/* Actions / missing */}
              <Col gap={16} style={{ width: 320, flexShrink: 0 }}>
                {data.missing_items && data.missing_items.length > 0 && (
                  <Card>
                    <Eyebrow color={P.fail} style={{ marginBottom: 10 }}>Missing</Eyebrow>
                    <Col gap={6}>
                      {data.missing_items.map((item, i) => (
                        <Row key={i} gap={8} style={{ alignItems: 'flex-start' }}>
                          <span style={{ color: P.fail, fontSize: 11, marginTop: 2 }}>✕</span>
                          <Text size={12} color={P.textDim}>{item}</Text>
                        </Row>
                      ))}
                    </Col>
                  </Card>
                )}

                {data.recommended_actions && data.recommended_actions.length > 0 && (
                  <Card>
                    <Eyebrow color={P.accent} style={{ marginBottom: 10 }}>Recommended actions</Eyebrow>
                    <Col gap={8}>
                      {data.recommended_actions.map((action, i) => (
                        <div key={i} style={{
                          padding: '8px 12px', borderRadius: 8,
                          background: P.cardHi, border: `1px solid ${P.border}`,
                        }}>
                          <Text size={12}>{action}</Text>
                        </div>
                      ))}
                    </Col>
                  </Card>
                )}
              </Col>
            </Row>

            {/* Driver readiness grid */}
            {data.driver_readiness && data.driver_readiness.length > 0 && (
              <div>
                <Eyebrow style={{ marginBottom: 12 }}>Driver readiness</Eyebrow>
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
                  gap: 12,
                }}>
                  {data.driver_readiness.map((dr, i) => <DriverCard key={i} dr={dr} />)}
                </div>
              </div>
            )}
          </>
        )}
      </Col>
    </Screen>
  )
}
