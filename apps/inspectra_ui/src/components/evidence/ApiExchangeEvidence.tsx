import { useState } from 'react';
import { F, P } from '../../design/tokens';
import type { EvidenceFile } from '../../types/api';

interface ApiExchangeEvidenceProps {
  request?: EvidenceFile;
  response?: EvidenceFile;
  assertion?: EvidenceFile;
}

function pretty(value: unknown): string {
  if (value === undefined || value === null || value === '') return '—';
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2);
}

function ExchangeBody({ evidence, mode }: { evidence?: EvidenceFile; mode: 'request' | 'response' }) {
  if (!evidence) return <div style={{ color: P.textMute, fontSize: 11 }}>No {mode} evidence captured.</div>;
  const metadata = evidence.metadata_json ?? {};
  const body = mode === 'request'
    ? (metadata.body_json ?? metadata.body)
    : (metadata.body_json ?? metadata.body_preview ?? metadata.body);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 11, color: P.textDim }}>
      {mode === 'request' && <div><strong style={{ color: P.text }}>{String(metadata.method ?? 'GET')}</strong> {String(metadata.url ?? '')}</div>}
      {mode === 'response' && <div><span style={{ color: P.textMute }}>Status</span> <strong style={{ color: P.text }}>{String(metadata.status_code ?? '—')}</strong></div>}
      {metadata.headers != null && (
        <pre style={{ margin: 0, padding: 9, borderRadius: 7, background: P.bg, border: `1px solid ${P.border}`, fontFamily: F.mono, fontSize: 10, whiteSpace: 'pre-wrap', wordBreak: 'break-word', color: P.textDim }}>{pretty(metadata.headers)}</pre>
      )}
      {body != null && (
        <pre style={{ margin: 0, maxHeight: 260, overflow: 'auto', padding: 9, borderRadius: 7, background: P.bg, border: `1px solid ${P.border}`, fontFamily: F.mono, fontSize: 10, whiteSpace: 'pre-wrap', wordBreak: 'break-word', color: P.text }}>{pretty(body)}</pre>
      )}
    </div>
  );
}

export function ApiExchangeEvidence({ request, response, assertion }: ApiExchangeEvidenceProps) {
  const [tab, setTab] = useState<'request' | 'response'>(request ? 'request' : 'response');
  const assertionMetadata = assertion?.metadata_json ?? {};
  return (
    <section aria-label="API request and response" style={{ borderTop: `1px solid ${P.border}`, paddingTop: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: P.text, marginBottom: 8 }}>API request / response</div>
      <div role="tablist" aria-label="API exchange" style={{ display: 'flex', gap: 4, marginBottom: 9 }}>
        {(['request', 'response'] as const).map((name) => (
          <button key={name} type="button" role="tab" aria-selected={tab === name} onClick={() => setTab(name)} style={{ padding: '5px 10px', borderRadius: 6, border: `1px solid ${tab === name ? P.accent : P.border}`, background: tab === name ? P.accentSoft : P.card, color: tab === name ? P.text : P.textMute, textTransform: 'capitalize', cursor: 'pointer' }}>{name}</button>
        ))}
      </div>
      <ExchangeBody evidence={tab === 'request' ? request : response} mode={tab} />
      {assertion && (
        <div style={{ marginTop: 9, padding: 9, borderRadius: 7, background: assertionMetadata.passed ? P.passSoft : P.failSoft, border: `1px solid ${assertionMetadata.passed ? P.pass : P.fail}33`, color: assertionMetadata.passed ? P.pass : P.fail, fontSize: 11 }}>
          {String(assertionMetadata.details ?? (assertionMetadata.passed ? 'Assertion passed' : 'Assertion failed'))}
        </div>
      )}
    </section>
  );
}
