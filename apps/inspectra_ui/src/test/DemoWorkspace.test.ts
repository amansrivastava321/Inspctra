import { describe, expect, it } from 'vitest';
import { generateDemoWorkspace } from '../mocks/sampleData';

describe('generateDemoWorkspace', () => {
  it('returns a complete deterministic workspace on every call', () => {
    const first = generateDemoWorkspace();
    const second = generateDemoWorkspace();

    expect(first).toEqual(second);
    expect(first.health).toEqual({ status: 'ok', provenance: 'DEMO_EXAMPLE' });
    expect(first.projects.length).toBeGreaterThan(0);
    expect(first.apps.length).toBeGreaterThan(0);
    expect(first.validationPacks.length).toBeGreaterThan(0);
    expect(first.liveRuns.length).toBeGreaterThan(0);
    expect(first.evidence.length).toBeGreaterThan(0);
    expect(first.reports.length).toBeGreaterThan(0);
  });

  it('labels every auditable demo artifact as DEMO_EXAMPLE', () => {
    const demo = generateDemoWorkspace();

    expect(demo.liveRuns.every(run => run.provenance === 'DEMO_EXAMPLE')).toBe(true);
    expect(demo.liveRuns.flatMap(run => run.step_results)
      .every(step => step.provenance === 'DEMO_EXAMPLE')).toBe(true);
    expect(demo.evidence.every(item => item.provenance === 'DEMO_EXAMPLE')).toBe(true);
    expect(demo.reports.every(item => item.provenance === 'DEMO_EXAMPLE')).toBe(true);
  });
});
