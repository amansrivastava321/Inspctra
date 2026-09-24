import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { PermissionModal } from '../components/modals/PermissionModal';
import type { PermissionRecord } from '../types/api';

const MOCK_PERM: PermissionRecord = {
  id: 'p1',
  run_id: 'r1',
  action_type: 'launch_app',
  description: 'Inspectra wants to launch FlowBook',
  what_will_happen: ['Open FlowBook', 'Take screenshot'],
  what_will_not: 'Inspectra will not modify your files',
  risk_level: 'low',
  status: 'pending',
};

describe('PermissionModal', () => {
  it('renders description', () => {
    const onApprove = vi.fn();
    const onDeny = vi.fn();
    render(
      <PermissionModal
        permission={MOCK_PERM}
        onApprove={onApprove}
        onDeny={onDeny}
        onClose={vi.fn()}
      />
    );
    expect(screen.getByText(/Inspectra wants to launch FlowBook/i)).toBeInTheDocument();
  });

  it('calls onApprove when approve clicked', () => {
    const onApprove = vi.fn();
    render(
      <PermissionModal
        permission={MOCK_PERM}
        onApprove={onApprove}
        onDeny={vi.fn()}
        onClose={vi.fn()}
      />
    );
    fireEvent.click(screen.getByText('Approve'));
    expect(onApprove).toHaveBeenCalledWith('p1');
  });

  it('calls onDeny when deny clicked', () => {
    const onDeny = vi.fn();
    render(
      <PermissionModal
        permission={MOCK_PERM}
        onApprove={vi.fn()}
        onDeny={onDeny}
        onClose={vi.fn()}
      />
    );
    fireEvent.click(screen.getByText('Deny'));
    expect(onDeny).toHaveBeenCalledWith('p1');
  });

  it('shows what_will_not safety notice', () => {
    render(
      <PermissionModal
        permission={MOCK_PERM}
        onApprove={vi.fn()}
        onDeny={vi.fn()}
        onClose={vi.fn()}
      />
    );
    expect(screen.getByText(/will not modify/i)).toBeInTheDocument();
  });
});
