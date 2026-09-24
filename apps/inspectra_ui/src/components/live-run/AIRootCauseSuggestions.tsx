import { useEffect, useState } from 'react';
import { BrainCircuit, ChevronRight } from 'lucide-react';

import {
  generateRunRootCauseSuggestions,
  getRunRootCauseSuggestions,
} from '../../api/client';
import { F, P } from '../../design/tokens';
import type {
  AIRootCauseEvidenceRef,
  AIRootCauseSuggestion,
  AIRootCauseSuggestionBatch,
} from '../../types/api';
import { ProvenanceBadge } from '../ProvenanceBadge';
import { Btn, Card } from '../layout/AppShell';

type SafeState = 'active' | 'no-failure' | 'not-found' | 'error' | null;

export interface AIRootCauseSuggestionsProps {
  runId: string;
  runStatus?: string;
  hasFailureSignal?: boolean;
  isDemo?: boolean;
  backendAvailable?: boolean;
  onSelectStep?: (stepId: string) => void;
}

const ACTIVE_STATUSES = new Set(['pending', 'queued', 'starting', 'running']);

function errorStatus(error: unknown): number | undefined {
  if (!error || typeof error !== 'object' || !('status' in error)) return undefined;
  return typeof error.status === 'number' ? error.status : undefined;
}

function conflictState(error: unknown): SafeState {
  if (errorStatus(error) === 404) return 'not-found';
  if (errorStatus(error) !== 409) return 'error';
  const message = error instanceof Error ? error.message.toLowerCase() : '';
  return message.includes('no failure signal') ? 'no-failure' : 'active';
}

function safeStateCopy(state: SafeState): string | null {
  if (state === 'active') return 'Possible-cause analysis is available after the run finishes.';
  if (state === 'no-failure') return 'No failure signal is available for root-cause analysis.';
  if (state === 'not-found') return 'Possible-cause analysis is unavailable for this run.';
  if (state === 'error') return 'Possible-cause analysis could not be generated.';
  return null;
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <span style={{ color: P.textMute, fontFamily: F.mono, fontSize: 10 }}>
      {children}
    </span>
  );
}

function StringSection({ title, items }: { title: string; items: string[] }) {
  return (
    <details style={{ borderTop: `1px solid ${P.border}`, paddingTop: 8 }}>
      <summary style={{ cursor: 'pointer', color: P.textDim, fontSize: 11, fontWeight: 600 }}>
        {title}
      </summary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginTop: 7 }}>
        {items.length > 0 ? items.map((item, index) => (
          <div key={`${title}-${index}`} style={{ color: P.textDim, fontSize: 11, lineHeight: 1.5 }}>
            <ChevronRight size={11} aria-hidden style={{ display: 'inline', marginRight: 4 }} />
            {item}
          </div>
        )) : (
          <span style={{ color: P.textMute, fontSize: 11 }}>None recorded.</span>
        )}
      </div>
    </details>
  );
}

function EvidenceReference({
  reference,
  onSelectStep,
}: {
  reference: AIRootCauseEvidenceRef;
  onSelectStep?: (stepId: string) => void;
}) {
  const label = `${reference.id} · ${reference.field}`;
  return (
    <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 7 }}>
      {reference.type === 'step_field' && onSelectStep ? (
        <button
          type="button"
          onClick={() => onSelectStep(reference.id)}
          style={{
            border: 0, padding: 0, background: 'transparent', color: P.accent,
            cursor: 'pointer', fontFamily: F.mono, fontSize: 10, textDecoration: 'underline',
          }}
        >
          {label}
        </button>
      ) : (
        <span style={{ color: P.textDim, fontFamily: F.mono, fontSize: 10 }}>{label}</span>
      )}
      <span style={{ color: P.textMute, fontSize: 9 }}>{reference.type.replace(/_/g, ' ')}</span>
      <ProvenanceBadge provenance={reference.provenance} source={`root cause reference ${reference.id}`} />
    </div>
  );
}

function SuggestionCard({
  suggestion,
  onSelectStep,
}: {
  suggestion: AIRootCauseSuggestion;
  onSelectStep?: (stepId: string) => void;
}) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 9, padding: 12,
      borderRadius: 8, border: `1px solid ${P.border}`, background: P.cardHi,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10 }}>
        <div>
          <div style={{ color: P.text, fontSize: 12, fontWeight: 650 }}>
            {suggestion.rank}. {suggestion.title}
          </div>
          <div style={{ color: P.textMute, fontSize: 10, marginTop: 3 }}>{suggestion.category}</div>
        </div>
        <ProvenanceBadge provenance={suggestion.source_provenance} source={`root cause ${suggestion.suggestion_id}`} />
      </div>

      <div style={{ color: P.textDim, fontSize: 12, lineHeight: 1.55 }}>
        {suggestion.possible_cause}
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
        <div><Label>confidence:</Label> <span style={{ color: P.text, fontSize: 11 }}>{Math.round(suggestion.confidence * 100)}%</span></div>
        <div><Label>generation:</Label> <span style={{ color: P.text, fontSize: 11 }}>{suggestion.generation_source}</span></div>
        <div><Label>owner:</Label> <span style={{ color: P.text, fontSize: 11 }}>{suggestion.suggested_owner_area.replace(/_/g, ' ')}</span></div>
      </div>

      <StringSection title="Supporting signals" items={suggestion.supporting_signals} />
      <StringSection title="Contradicting signals" items={suggestion.contradicting_signals} />
      <details style={{ borderTop: `1px solid ${P.border}`, paddingTop: 8 }}>
        <summary style={{ cursor: 'pointer', color: P.textDim, fontSize: 11, fontWeight: 600 }}>
          Evidence
        </summary>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 7, marginTop: 7 }}>
          {suggestion.evidence_refs.map((reference, index) => (
            <EvidenceReference
              key={`${reference.type}-${reference.id}-${reference.field}-${index}`}
              reference={reference}
              onSelectStep={onSelectStep}
            />
          ))}
        </div>
      </details>
      <StringSection title="Missing evidence" items={suggestion.missing_evidence} />
      <StringSection title="Recommended verification" items={suggestion.recommended_verification} />
    </div>
  );
}

export function AIRootCauseSuggestions({
  runId,
  runStatus,
  hasFailureSignal,
  isDemo = false,
  backendAvailable = true,
  onSelectStep,
}: AIRootCauseSuggestionsProps) {
  const [batch, setBatch] = useState<AIRootCauseSuggestionBatch | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [safeState, setSafeState] = useState<SafeState>(null);

  useEffect(() => {
    let active = true;
    setBatch(null);
    setSafeState(null);
    if (isDemo || !backendAvailable) {
      setLoading(false);
      return () => { active = false; };
    }
    setLoading(true);
    getRunRootCauseSuggestions(runId)
      .then(result => {
        if (active) setBatch(result);
      })
      .catch(error => {
        if (active) setSafeState(conflictState(error));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [backendAvailable, isDemo, runId]);

  const activeRun = ACTIVE_STATUSES.has((runStatus || '').toLowerCase());
  const noFailureSignal = hasFailureSignal === false;
  const existingAnalysis = Boolean(batch?.analysis_id);
  const hasSuggestions = Boolean(batch?.suggestions.length);
  const disabled = isDemo || !backendAvailable;

  const generate = async () => {
    if (disabled || activeRun || noFailureSignal || generating) return;
    setGenerating(true);
    setSafeState(null);
    try {
      setBatch(await generateRunRootCauseSuggestions(runId));
    } catch (error) {
      setSafeState(conflictState(error));
    } finally {
      setGenerating(false);
    }
  };

  const eligibilityState: SafeState = activeRun
    ? 'active'
    : noFailureSignal
      ? 'no-failure'
      : safeState;
  const stateCopy = safeStateCopy(eligibilityState);

  return (
    <Card>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: P.text, fontSize: 11, fontWeight: 650 }}>
              <BrainCircuit size={14} color={P.accent} aria-hidden />
              AI Possible Causes
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 7 }}>
              <span style={{
                fontSize: 9, fontWeight: 700, fontFamily: F.mono, color: P.accent,
                background: P.accentSoft, border: `1px solid ${P.borderFocus}`,
                borderRadius: 4, padding: '2px 6px',
              }}>
                AI Draft — Possible Cause
              </span>
              <span style={{
                fontSize: 9, fontWeight: 700, fontFamily: F.mono, color: P.textDim,
                background: P.cardHi, border: `1px solid ${P.borderHi}`,
                borderRadius: 4, padding: '2px 6px',
              }}>
                Non-authoritative
              </span>
            </div>
          </div>
          {batch?.source_provenance && (
            <ProvenanceBadge provenance={batch.source_provenance} source="root cause analysis" />
          )}
        </div>

        <div style={{ color: P.textDim, fontSize: 11 }}>
          This is a hypothesis. It does not change the run verdict or fix the app.
        </div>

        {loading && <div style={{ color: P.textMute, fontSize: 11 }}>Loading existing possible-cause analysis…</div>}

        {!loading && !hasSuggestions && stateCopy && (
          <div role="status" style={{ color: eligibilityState === 'error' ? P.fail : P.textDim, fontSize: 11 }}>
            {stateCopy}
          </div>
        )}

        {!loading && !stateCopy && batch?.status === 'inconclusive' && existingAnalysis && !hasSuggestions && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
            <div style={{ color: P.textDim, fontSize: 11 }}>
              Insufficient evidence to suggest a reliable possible cause.
            </div>
            <StringSection title="Missing evidence" items={batch.missing_evidence} />
          </div>
        )}

        {!loading && !stateCopy && !existingAnalysis && !hasSuggestions && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 8 }}>
            <div style={{ color: P.textMute, fontSize: 11 }}>
              No AI root-cause analysis has been generated for this run.
            </div>
            <Btn
              variant="secondary"
              disabled={disabled || generating}
              title={isDemo
                ? 'Available in your real workspace. Leave demo to get started.'
                : !backendAvailable
                  ? 'Backend offline.'
                  : undefined}
              onClick={generate}
            >
              {generating ? 'Analyzing available evidence…' : 'Suggest possible causes'}
            </Btn>
          </div>
        )}

        {generating && existingAnalysis && (
          <div style={{ color: P.textMute, fontSize: 11 }}>Analyzing available evidence…</div>
        )}

        {hasSuggestions && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {batch!.suggestions.map(suggestion => (
              <SuggestionCard
                key={suggestion.suggestion_id}
                suggestion={suggestion}
                onSelectStep={onSelectStep}
              />
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}
