import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { StatusBadge } from '../components/status/StatusBadge';

describe('StatusBadge', () => {
  it('renders PASS badge', () => {
    render(<StatusBadge kind="pass" />);
    expect(screen.getByText('PASS')).toBeInTheDocument();
  });

  it('renders FAIL badge', () => {
    render(<StatusBadge kind="fail" />);
    expect(screen.getByText('FAIL')).toBeInTheDocument();
  });

  it('renders UNCLEAR badge', () => {
    render(<StatusBadge kind="unclear" />);
    expect(screen.getByText('UNCLEAR')).toBeInTheDocument();
  });

  it('renders unknown kind with uppercase label', () => {
    render(<StatusBadge kind="custom_status" />);
    expect(screen.getByText('CUSTOM_STATUS')).toBeInTheDocument();
  });
});
