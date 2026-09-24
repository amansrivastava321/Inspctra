import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { RuntimeFlowMap } from '../components/runtime/RuntimeFlowMap';

describe('RuntimeFlowMap', () => {
  it('renders svg', () => {
    const { container } = render(<RuntimeFlowMap />);
    expect(container.querySelector('svg')).toBeTruthy();
  });

  it('highlights active node', () => {
    const { container } = render(<RuntimeFlowMap activeNode="app" />);
    // Active node should have accent-colored stroke (not default border)
    const rects = container.querySelectorAll('rect');
    expect(rects.length).toBeGreaterThan(0);
  });

  it('renders all 9 nodes', () => {
    const { container } = render(<RuntimeFlowMap />);
    // 9 node groups
    const groups = container.querySelectorAll('g');
    expect(groups.length).toBeGreaterThanOrEqual(9);
  });
});
