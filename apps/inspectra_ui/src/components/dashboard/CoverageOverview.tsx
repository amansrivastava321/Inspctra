import { Boxes, FolderKanban, PackageCheck } from 'lucide-react';
import { P, F } from '../../design/tokens';
import type { DashboardCoverage, Provenance } from '../../types/api';
import { Card } from '../layout/AppShell';
import { ProvenanceBadge } from '../ProvenanceBadge';
import { relativeTime } from './DashboardHero';

interface CoverageOverviewProps {
  projects: number;
  apps: number;
  packs: number;
  coverage: DashboardCoverage;
  provenance?: Provenance | null;
}

const METRICS = [
  { key: 'projects', label: 'Projects', icon: FolderKanban },
  { key: 'apps', label: 'Apps', icon: Boxes },
  { key: 'packs', label: 'Validation packs', icon: PackageCheck },
] as const;

export function CoverageOverview({ projects, apps, packs, coverage, provenance }: CoverageOverviewProps) {
  const values = { projects, apps, packs };
  return (
    <section aria-labelledby="coverage-heading">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <h2 id="coverage-heading" style={{ margin: 0, fontSize: 18, color: P.text }}>Coverage Overview</h2>
        <ProvenanceBadge provenance={coverage.provenance ?? provenance} source="Dashboard coverage" />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12, marginBottom: 12 }}>
        {METRICS.map(metric => {
          const Icon = metric.icon;
          return (
            <Card key={metric.key}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Icon size={16} color={P.accent} />
                <ProvenanceBadge provenance={provenance} source={`Dashboard ${metric.label} metric`} />
              </div>
              <div style={{ fontSize: 27, fontWeight: 700, color: P.text, marginTop: 14 }}>{values[metric.key]}</div>
              <div style={{ color: P.textMute, fontSize: 11, fontFamily: F.mono, textTransform: 'uppercase', marginTop: 4 }}>{metric.label}</div>
            </Card>
          );
        })}
      </div>
      <Card>
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 20 }}>
          <div style={{ flex: 1 }}>
            <div style={{ color: P.text, fontSize: 14, fontWeight: 600 }}>
              {coverage.with_packs} of {coverage.total} apps have validation packs
            </div>
            <div style={{ height: 8, borderRadius: 999, background: P.cardHi, marginTop: 12, overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${Math.max(0, Math.min(100, coverage.percentage ?? 0))}%`, background: P.accent, borderRadius: 999 }} />
            </div>
          </div>
          <div style={{ textAlign: 'right', flexShrink: 0 }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: P.text }}>
              {coverage.percentage == null ? '—' : `${coverage.percentage}%`}
            </div>
            <div style={{ color: P.textMute, fontSize: 11, marginTop: 4 }}>
              {coverage.last_pack_created_at
                ? `Last pack created ${relativeTime(coverage.last_pack_created_at)}`
                : 'No packs created yet'}
            </div>
          </div>
        </div>
      </Card>
    </section>
  );
}
