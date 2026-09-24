import { useState } from 'react'
import { listEvidence, downloadEvidenceUrl } from '../api/client'
import { useApi } from '../hooks/useApi'
import {
  Screen, Card, Row, Col, Text, Eyebrow, Button,
  LoadingSpinner, ErrorBanner, EmptyState,
} from '../design/components'
import { P, F } from '../design/tokens'

const MIME_ICON: Record<string, string> = {
  'image/png': '🖼', 'image/jpeg': '🖼', 'image/gif': '🖼', 'image/webp': '🖼',
  'video/mp4': '🎬', 'video/webm': '🎬',
  'application/json': '{}', 'text/plain': '📄', 'text/html': '🌐',
  'application/pdf': '📑',
}

const FILTER_TABS = ['All', 'Images', 'Video', 'JSON', 'Other']

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

function mimeToFilter(mime: string) {
  if (mime.startsWith('image/')) return 'Images'
  if (mime.startsWith('video/')) return 'Video'
  if (mime.includes('json')) return 'JSON'
  return 'Other'
}

export default function Evidence() {
  const [tab, setTab] = useState('All')
  const [preview, setPreview] = useState<string | null>(null)
  const { data: evidence, loading, error, refetch } = useApi(listEvidence)

  const filtered = (evidence || []).filter(e =>
    tab === 'All' || mimeToFilter(e.mime_type) === tab
  )

  const counts: Record<string, number> = { All: evidence?.length ?? 0 }
  for (const e of evidence ?? []) {
    const f = mimeToFilter(e.mime_type)
    counts[f] = (counts[f] || 0) + 1
  }

  return (
    <Screen
      title="Evidence Center"
      sub={evidence ? `${evidence.length} artifact${evidence.length !== 1 ? 's' : ''}` : undefined}
      right={<Button variant="ghost" onClick={refetch}>↻</Button>}
    >
      <Col gap={16}>
        {/* Filter tabs */}
        <Row gap={4}>
          {FILTER_TABS.map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              padding: '6px 14px', borderRadius: 8, cursor: 'pointer',
              fontFamily: F.ui, fontSize: 12,
              background: tab === t ? P.accentSoft : 'transparent',
              border: `1px solid ${tab === t ? P.accent : P.border}`,
              color: tab === t ? P.text : P.textDim,
            }}>
              {t}
              {counts[t] !== undefined && (
                <span style={{ marginLeft: 6, fontFamily: F.mono, color: tab === t ? P.accent : P.textMute }}>
                  {counts[t]}
                </span>
              )}
            </button>
          ))}
        </Row>

        {loading ? <LoadingSpinner /> : error ? <ErrorBanner message={error} /> : filtered.length === 0 ? (
          <EmptyState message="No evidence artifacts yet. Run a test pack to generate evidence." />
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
            gap: 12,
          }}>
            {filtered.map(ev => {
              const icon = MIME_ICON[ev.mime_type] || '📎'
              const isImage = ev.mime_type.startsWith('image/')
              const downloadUrl = downloadEvidenceUrl(ev.id)
              return (
                <Card key={ev.id} pad={0} style={{ overflow: 'hidden', cursor: 'pointer' }}
                  onClick={() => isImage ? setPreview(downloadUrl) : window.open(downloadUrl, '_blank')}>
                  {/* Thumbnail area */}
                  <div style={{
                    height: 120, background: P.cardHi,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    borderBottom: `1px solid ${P.border}`,
                    position: 'relative',
                    overflow: 'hidden',
                  }}>
                    {isImage ? (
                      <img
                        src={downloadUrl}
                        alt={ev.name}
                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                        onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                      />
                    ) : (
                      <span style={{ fontSize: 36, opacity: 0.5 }}>{icon}</span>
                    )}
                    {/* Overlay on hover */}
                    <div style={{
                      position: 'absolute', inset: 0,
                      background: 'rgba(0,0,0,0)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      transition: 'background 0.15s',
                    }}
                      onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.background = 'rgba(0,0,0,0.4)' }}
                      onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.background = 'rgba(0,0,0,0)' }}
                    >
                      <span style={{ color: '#fff', opacity: 0, fontSize: 22, transition: 'opacity 0.15s' }}
                        onMouseEnter={e => { (e.currentTarget as HTMLElement).style.opacity = '1' }}
                      >
                        {isImage ? '🔍' : '⬇'}
                      </span>
                    </div>
                  </div>

                  {/* Meta */}
                  <div style={{ padding: '10px 12px' }}>
                    <Text size={12} weight={500} style={{
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>{ev.name}</Text>
                    <Row gap={6} style={{ marginTop: 4, justifyContent: 'space-between' }}>
                      <span style={{
                        padding: '1px 7px', borderRadius: 99,
                        fontFamily: F.mono, fontSize: 9.5,
                        background: P.cardHi, border: `1px solid ${P.border}`,
                        color: P.textMute,
                      }}>{ev.mime_type.split('/')[1] || ev.mime_type}</span>
                      <Text size={10} color={P.textMute} mono>{formatBytes(ev.size_bytes)}</Text>
                    </Row>
                    <Text size={10} color={P.textMute} style={{ marginTop: 4 }}>
                      {new Date(ev.created_at).toLocaleString()}
                    </Text>
                  </div>
                </Card>
              )
            })}
          </div>
        )}
      </Col>

      {/* Image lightbox */}
      {preview && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.9)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 2000, cursor: 'zoom-out',
        }} onClick={() => setPreview(null)}>
          <img src={preview} alt="preview" style={{ maxWidth: '90vw', maxHeight: '90vh', borderRadius: 8 }} />
          <button onClick={() => setPreview(null)} style={{
            position: 'absolute', top: 24, right: 28,
            background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.2)',
            color: '#fff', borderRadius: 8, padding: '6px 12px', cursor: 'pointer',
            fontFamily: F.ui, fontSize: 13,
          }}>✕ Close</button>
        </div>
      )}
    </Screen>
  )
}
