import { listReports, exportReportUrl } from '../api/client'
import { useApi } from '../hooks/useApi'
import {
  Screen, Card, Row, Col, Text, Eyebrow, Button,
  LoadingSpinner, ErrorBanner, EmptyState,
} from '../design/components'
import { P, F } from '../design/tokens'

const FORMAT_COLORS: Record<string, string> = {
  json: P.accent,
  pdf: '#f472b6',
  html: '#34d399',
  csv: '#fbbf24',
  markdown: P.textDim,
}

const FORMAT_ICONS: Record<string, string> = {
  json: '{}',
  pdf: '📑',
  html: '🌐',
  csv: '📊',
  markdown: '📝',
}

export default function Reports() {
  const { data: reports, loading, error, refetch } = useApi(listReports)

  return (
    <Screen
      title="Reports"
      sub={reports ? `${reports.length} report${reports.length !== 1 ? 's' : ''}` : undefined}
      right={<Button variant="ghost" onClick={refetch}>↻</Button>}
    >
      {loading ? <LoadingSpinner /> : error ? <ErrorBanner message={error} /> : !reports?.length ? (
        <EmptyState message="No reports generated yet. Complete a test run to generate reports." />
      ) : (
        <Card pad={0}>
          {/* Table header */}
          <div style={{
            display: 'grid', gridTemplateColumns: '40px 2fr 1fr 100px 140px 100px',
            padding: '10px 20px', borderBottom: `1px solid ${P.border}`,
          }}>
            {['', 'Report', 'Run', 'Format', 'Generated', ''].map((h, i) => (
              <Eyebrow key={i}>{h}</Eyebrow>
            ))}
          </div>

          {reports.map((report, idx) => {
            const fmtColor = FORMAT_COLORS[report.format] || P.textMute
            const fmtIcon = FORMAT_ICONS[report.format] || '📄'
            const exportUrl = exportReportUrl(report.id)
            return (
              <div
                key={report.id}
                style={{
                  display: 'grid', gridTemplateColumns: '40px 2fr 1fr 100px 140px 100px',
                  padding: '14px 20px', alignItems: 'center',
                  borderBottom: idx < reports.length - 1 ? `1px solid ${P.border}` : 'none',
                }}
              >
                {/* Format icon */}
                <div style={{
                  width: 30, height: 30, borderRadius: 8,
                  background: `${fmtColor}18`, border: `1px solid ${fmtColor}33`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 14,
                }}>{fmtIcon}</div>

                {/* Name */}
                <Col gap={2}>
                  <Text size={13} weight={500}>{report.name}</Text>
                  <Text size={11} color={P.textMute} mono>{report.relative_path}</Text>
                </Col>

                {/* Run ID */}
                <Text size={12} color={P.textDim} mono>{report.run_id.slice(0, 8)}</Text>

                {/* Format badge */}
                <span style={{
                  display: 'inline-flex', padding: '2px 10px', borderRadius: 99,
                  fontFamily: F.mono, fontSize: 10,
                  background: `${fmtColor}18`, border: `1px solid ${fmtColor}33`,
                  color: fmtColor, alignSelf: 'center',
                }}>{report.format.toUpperCase()}</span>

                {/* Created */}
                <Text size={11} color={P.textMute} mono>
                  {new Date(report.created_at).toLocaleString()}
                </Text>

                {/* Export */}
                <Row gap={6}>
                  <a href={exportUrl} target="_blank" rel="noopener noreferrer"
                    style={{ textDecoration: 'none' }}>
                    <Button size="sm" variant="primary">⬇ Export</Button>
                  </a>
                </Row>
              </div>
            )
          })}
        </Card>
      )}
    </Screen>
  )
}
