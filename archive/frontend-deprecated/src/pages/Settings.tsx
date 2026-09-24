import { useState, useEffect } from 'react'
import { listSettings, setSetting } from '../api/client'
import { useApi } from '../hooks/useApi'
import {
  Screen, Card, Row, Col, Text, Eyebrow, Button,
  LoadingSpinner, ErrorBanner,
} from '../design/components'
import { P, F } from '../design/tokens'
import type { ProductSetting } from '../api/types'

const SETTING_GROUPS = [
  {
    title: 'General',
    keys: ['dashboard_title', 'theme'],
  },
  {
    title: 'Execution',
    keys: ['default_timeout_seconds', 'run_concurrency_limit'],
  },
  {
    title: 'Storage',
    keys: ['artifacts_dir', 'auto_index_artifacts'],
  },
  {
    title: 'Diagnostics',
    keys: ['log_level', 'enable_runtime_doctor'],
  },
]

const SETTING_META: Record<string, { label: string; desc: string; type: 'text' | 'toggle' | 'select' | 'number'; options?: string[] }> = {
  dashboard_title:        { label: 'Dashboard title',        desc: 'Display name shown in the workspace header',         type: 'text' },
  theme:                  { label: 'Theme',                   desc: 'UI color scheme (dark only in this build)',           type: 'select', options: ['dark'] },
  default_timeout_seconds:{ label: 'Default step timeout',    desc: 'Seconds before a test step times out',               type: 'number' },
  run_concurrency_limit:  { label: 'Max concurrent runs',     desc: 'Maximum number of simultaneous live test runs',       type: 'number' },
  artifacts_dir:          { label: 'Artifacts directory',     desc: 'Local path where test artifacts are stored',          type: 'text' },
  auto_index_artifacts:   { label: 'Auto-index artifacts',    desc: 'Automatically register new artifact files',          type: 'toggle' },
  log_level:              { label: 'Log level',               desc: 'Verbosity of application logs',                      type: 'select', options: ['DEBUG', 'INFO', 'WARNING', 'ERROR'] },
  enable_runtime_doctor:  { label: 'Enable Runtime Doctor',   desc: 'Show environment health checks in sidebar',          type: 'toggle' },
}

function SettingRow({ setting, onSave }: { setting: ProductSetting; onSave: () => void }) {
  const meta = SETTING_META[setting.key]
  const [value, setValue] = useState(setting.value)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [err, setErr] = useState('')
  const dirty = value !== setting.value

  const save = async () => {
    setSaving(true); setErr('')
    try {
      await setSetting(setting.key, value)
      setSaved(true); setTimeout(() => setSaved(false), 2000)
      onSave()
    } catch (e: any) { setErr(e.message) }
    finally { setSaving(false) }
  }

  if (!meta) return null

  return (
    <Row style={{ padding: '14px 20px', alignItems: 'center', gap: 16, borderBottom: `1px solid ${P.border}` }}>
      <Col gap={3} style={{ flex: 1 }}>
        <Text size={13} weight={500}>{meta.label}</Text>
        <Text size={11} color={P.textMute}>{meta.desc}</Text>
        {err && <Text size={11} color={P.fail}>{err}</Text>}
      </Col>

      {/* Control */}
      {meta.type === 'toggle' ? (
        <button onClick={() => {
          const next = value === 'true' ? 'false' : 'true'
          setValue(next)
          setSetting(setting.key, next).then(onSave).catch(e => setErr(e.message))
        }} style={{
          width: 44, height: 24, borderRadius: 99, cursor: 'pointer',
          background: value === 'true' ? P.accent : P.cardHi,
          border: `1px solid ${value === 'true' ? P.accent : P.border}`,
          position: 'relative', flexShrink: 0,
          transition: 'background 0.2s, border-color 0.2s',
        }}>
          <div style={{
            width: 18, height: 18, borderRadius: 99,
            background: '#fff', position: 'absolute',
            top: 2, left: value === 'true' ? 22 : 2,
            transition: 'left 0.2s',
            boxShadow: '0 1px 3px rgba(0,0,0,0.4)',
          }} />
        </button>
      ) : meta.type === 'select' ? (
        <Row gap={8} style={{ alignItems: 'center' }}>
          <select value={value} onChange={e => setValue(e.target.value)} style={{
            background: P.cardHi, border: `1px solid ${dirty ? P.accent : P.border}`,
            borderRadius: 8, padding: '6px 10px', color: P.text,
            fontFamily: F.ui, fontSize: 12, outline: 'none', cursor: 'pointer',
          }}>
            {(meta.options || []).map(o => <option key={o} value={o}>{o}</option>)}
          </select>
          {dirty && (
            <Button size="sm" variant="primary" onClick={save} disabled={saving}>
              {saving ? '…' : saved ? '✓' : 'Save'}
            </Button>
          )}
        </Row>
      ) : (
        <Row gap={8} style={{ alignItems: 'center' }}>
          <input
            type={meta.type === 'number' ? 'number' : 'text'}
            value={value}
            onChange={e => setValue(e.target.value)}
            style={{
              background: P.cardHi,
              border: `1px solid ${dirty ? P.accent : P.border}`,
              borderRadius: 8, padding: '6px 10px', color: P.text,
              fontFamily: meta.type === 'number' ? F.mono : F.ui, fontSize: 13,
              outline: 'none', width: meta.type === 'number' ? 80 : 200,
              transition: 'border-color 0.15s',
            }}
          />
          {dirty && (
            <Button size="sm" variant="primary" onClick={save} disabled={saving}>
              {saving ? '…' : saved ? '✓' : 'Save'}
            </Button>
          )}
          {saved && <Text size={11} color={P.pass} mono>Saved</Text>}
        </Row>
      )}
    </Row>
  )
}

export default function Settings() {
  const { data: settings, loading, error, refetch } = useApi(listSettings)

  const settingsMap: Record<string, ProductSetting> = {}
  for (const s of settings ?? []) settingsMap[s.key] = s

  return (
    <Screen
      title="Settings"
      sub="Workspace configuration"
      right={<Button variant="ghost" onClick={refetch}>↻</Button>}
    >
      {loading ? <LoadingSpinner /> : error ? <ErrorBanner message={error} /> : (
        <Col gap={24}>
          {SETTING_GROUPS.map(group => {
            const groupSettings = group.keys
              .map(k => settingsMap[k])
              .filter(Boolean)

            if (groupSettings.length === 0) return null

            return (
              <div key={group.title}>
                <Eyebrow style={{ marginBottom: 12 }}>{group.title}</Eyebrow>
                <Card pad={0}>
                  {groupSettings.map((s, i) => (
                    <div key={s.key} style={i === groupSettings.length - 1 ? { borderBottom: 'none' } : {}}>
                      <SettingRow setting={s} onSave={refetch} />
                    </div>
                  ))}
                </Card>
              </div>
            )
          })}

          {/* About card */}
          <div>
            <Eyebrow style={{ marginBottom: 12 }}>About</Eyebrow>
            <Card>
              <Row gap={16} style={{ alignItems: 'center' }}>
                <div style={{
                  width: 44, height: 44, borderRadius: 12,
                  background: `linear-gradient(135deg, ${P.accent}, #8b5cf6)`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: '#fff', fontFamily: F.display, fontWeight: 700, fontSize: 22,
                  boxShadow: `0 4px 12px -4px ${P.accent}66`,
                  flexShrink: 0,
                }}>i</div>
                <Col gap={3}>
                  <Text size={14} weight={600}>Inspectra QA Platform</Text>
                  <Text size={12} color={P.textDim}>Local workspace — running on 127.0.0.1:8765</Text>
                  <Text size={11} color={P.textMute} mono>React + FastAPI + SQLite</Text>
                </Col>
              </Row>
            </Card>
          </div>
        </Col>
      )}
    </Screen>
  )
}
