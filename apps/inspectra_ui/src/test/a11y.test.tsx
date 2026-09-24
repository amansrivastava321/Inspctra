/**
 * Automated accessibility scan using axe-core via jest-axe.
 * Covers pure UI components that don't require API mocking.
 * Zero critical violations expected.
 */
import { render } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import { describe, it, expect } from 'vitest';
import { EmptyState, BlockedState, PartialConfigBanner } from '../components/common/EmptyState';
import { StatusBadge } from '../components/status/StatusBadge';

expect.extend(toHaveNoViolations);

describe('Accessibility — zero critical violations', () => {
  it('EmptyState has no violations', async () => {
    const { container } = render(
      <EmptyState title="No data yet" description="Add an item to get started." />,
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('BlockedState has no violations', async () => {
    const { container } = render(
      <BlockedState
        title="Connect an app first"
        description="You need at least one app before running tests."
      />,
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('PartialConfigBanner has no violations', async () => {
    const { container } = render(
      <PartialConfigBanner message="This app has no validation packs." />,
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('StatusBadge (pass) has no violations', async () => {
    const { container } = render(<StatusBadge kind="pass" />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('StatusBadge (fail) has no violations', async () => {
    const { container } = render(<StatusBadge kind="fail" />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('StatusBadge (unclear) has no violations', async () => {
    const { container } = render(<StatusBadge kind="unclear" />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
