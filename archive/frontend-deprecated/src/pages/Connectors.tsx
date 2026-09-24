import { useState } from 'react'
import { getConnectors } from '../api/client'
import { useApi } from '../hooks/useApi'
import {
  Screen, Card, Row, Col, Display, Text, Eyebrow, Pill, Button,
  Meter, LoadingSpinner, ErrorBanner, EmptyState,
} from '../design/components'
import { P, F } from '../design/tokens'
import type { ConnectorInfo } from '../api/types'

const CONNECTOR_ICONS: Record<string, string> = {
  playwright: '🎭',
  appium: '📱',
  ollama: '🦙',
  vision: '👁',
  npm: '📦',
  default: '🔌',
}

const CONNECTOR_DESC: Record<string, string> = {
  playwright: 'Web browser automation — Chrome, Firefox, Safari',
  appium: 'Mobile & native app automation — iOS / Android / Windows / macOS',
  ollama: 'Local LLM inference — reasoning + vision',
  vision: 'Vision model for screenshot understanding',
  npm: 'Node package manager — required for Appium & drivers',
}

function ConnectorPanel({ connector }: { connector: ConnectorInfo }) {
  return (
    <Card elevated style={{
      borderLeft: `3px solid ${connector.ready ? P.pass : P.fail}`,
    }}>
      <Row style={{ alignItems: 'flex-start', gap: 14 }}>
        {/* Icon */}
        <div style={{
          width: 44, height: 44, borderRadius: 12, flexShrink: 0,
          background: connector.ready ? `${P.pass}18` : `${P.fail}18`,
          border: `1px solid ${connector.ready ? P.pass : P.fail}33`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 20,
        }}>
          {CONNECTOR_ICONS[connector.connector_type] || CONNECTOR_ICONS.default}
        </div>

        {/* Info */}
        <Col gap={4} style={{ flex: 1 }}>
          <Row gap={10} style={{ alignItems: 'center' }}>
            <Text size={14} weight={600}>{connector.connector_type}</Text>
            <Pill kind={connector.ready ? 'pass' : 'fail'} small>
              {connector.ready ? 'CONNECTED' : 'NOT READY'}
            </Pill>
          </Row>
          <Text size={12} color={P.textDim}>
            {CONNECTOR_DESC[connector.connector_type] || connector.connector_type}
          </Text>
          {connector.details && (
            <Text size={11} color={P.textMute} mono>{connector.details}</Text>
          )}
          {connector.checked_at && (
            <Text size={10} color={P.textMute}>Checked {new Date(connector.checked_at).toLocaleTimeString()}</Text>
          )}
        </Col>

        {/* Status dot (large) */}
        <div style={{
          width: 12, height: 12, borderRadius: 99, flexShrink: 0, marginTop: 4,
          background: connector.ready ? P.pass : P.fail,
          boxShadow: connector.ready ? `0 0 10px ${P.pass}88` : 'none',
        }} />
      </Row>
    </Card>
  )
}

export default function Connectors() {
  const [selected, setSelected] = useState<ConnectorInfo | null>(null)
  const { data, loading, error, refetch } = useApi(getConnectors)

  const readyCount = data?.ready ?? 0
  const totalCount = data?.total ?? 0
  const healthPct = totalCount > 0 ? Math.round((readyCount / totalCount) * 100) : 0

  const ready = (data?.connectors || []).filter(c => c.ready)
  const notReady = (data?.connectors || []).filter(c => !c.ready)

  return (
    <Screen
      title="Connectors"
      sub="Runtime dependencies for test execution"
      right={
        <Row gap={8}>
          <Button variant="ghost" onClick={refetch}>↻ Re-check</Button>
        </Row>
      }
    >
      <Col gap={20}>
        {loading ? <LoadingSpinner /> : error ? <ErrorBanner message={error} /> : !data ? null : (
          <>
            {/* Summary bar */}
            <Card>
              <Row gap={28} style={{ alignItems: 'center' }}>
                <Col gap={6} style={{ width: 200, flexShrink: 0 }}>
                  <Eyebrow>Connector health</Eyebrow>
                  <Row gap={8} style={{ alignItems: 'baseline' }}>
                    <Display size={40} weight={700} style={{
                      color: healthPct >= 80 ? P.pass : healthPct >= 50 ? P.unclear : P.fail,
                    }}>{readyCount}</Display>
                    <Text size={14} color={P.textDim}>/ {totalCount}</Text>
                  </Row>
                  <Meter
                    value={healthPct}
                    color={healthPct >= 80 ? P.pass : healthPct >= 50 ? P.unclear : P.fail}
                    height={5}
                  />
                </Col>
                <div style={{ width: 1, height: 60, background: P.border, flexShrink: 0 }} />
                <Row gap={20} style={{ flex: 1 }}>
                  <Col gap={4}>
                    <Eyebrow>Ready</Eyebrow>
                    <Text size={22} mono weight={600} style={{ color: P.pass }}>{readyCount}</Text>
                  </Col>
                  <Col gap={4}>
                    <Eyebrow>Not ready</Eyebrow>
                    <Text size={22} mono weight={600} style={{ color: notReady.length > 0 ? P.fail : P.textMute }}>
                      {notReady.length}
                    </Text>
                  </Col>
                  <Col gap={4}>
                    <Eyebrow>Checked at</Eyebrow>
                    <Text size={12} mono color={P.textDim}>
                      {data.checked_at ? new Date(data.checked_at).toLocaleTimeString() : '—'}
                    </Text>
                  </Col>
                </Row>
              </Row>
            </Card>

            {/* Not ready first */}
            {notReady.length > 0 && (
              <div>
                <Eyebrow color={P.fail} style={{ marginBottom: 10 }}>Needs attention ({notReady.length})</Eyebrow>
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
                  gap: 12,
                }}>
                  {notReady.map(c => (
                    <div key={c.connector_id} onClick={() => setSelected(selected?.connector_id === c.connector_id ? null : c)}
                      style={{ cursor: 'pointer' }}>
                      <ConnectorPanel connector={c} />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Ready connectors */}
            {ready.length > 0 && (
              <div>
                <Eyebrow color={P.pass} style={{ marginBottom: 10 }}>Connected ({ready.length})</Eyebrow>
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
                  gap: 12,
                }}>
                  {ready.map(c => <ConnectorPanel key={c.connector_id} connector={c} />)}
                </div>
              </div>
            )}

            {data.connectors.length === 0 && (
              <EmptyState message="No connectors detected. Run a health check to scan your environment." />
            )}
          </>
        )}
      </Col>
    </Screen>
  )
}
