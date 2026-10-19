import { describe, expect, it } from 'vitest';
import { P } from '../design/tokens';

function luminance(hex: string): number {
  const channels = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const AA_TEXT = 4.5;
const SURFACES = [P.bg, P.surface, P.card, P.cardHi] as const;

describe('design tokens meet WCAG AA text contrast', () => {
  it.each(['text', 'textDim', 'textMute', 'textFaint', 'skipped'] as const)('%s is readable on every surface', name => {
    for (const surface of SURFACES) {
      expect(contrast(P[name], surface), `${name} on ${surface}`).toBeGreaterThanOrEqual(AA_TEXT);
    }
  });

  it('white text is readable on solid accent fills', () => {
    expect(contrast('#ffffff', P.accentSolid)).toBeGreaterThanOrEqual(AA_TEXT);
  });
});
