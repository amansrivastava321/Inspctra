import { act, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useRunStream } from '../hooks/useRunStream';

const mocks = vi.hoisted(() => ({ createRunStream: vi.fn() }));
vi.mock('../api/client', () => ({ createRunStream: mocks.createRunStream }));

class FakeEventSource {
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close = vi.fn();
  private listeners = new Map<string, Array<(event: MessageEvent) => void>>();

  addEventListener(type: string, listener: (event: MessageEvent) => void) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  emit(type: string, payload: Record<string, unknown>) {
    const event = { type, data: JSON.stringify(payload) } as MessageEvent;
    for (const listener of this.listeners.get(type) ?? []) listener(event);
  }
}

function Harness() {
  const stream = useRunStream('run-1', true);
  return <div>{stream.terminal ? 'terminal' : 'active'}</div>;
}

describe('useRunStream completion', () => {
  let source: FakeEventSource;

  beforeEach(() => {
    source = new FakeEventSource();
    mocks.createRunStream.mockReturnValue(source as unknown as EventSource);
  });

  it('marks the stream terminal and closes it when the backend sends done', () => {
    render(<Harness />);
    expect(screen.getByText('active')).toBeInTheDocument();

    act(() => source.emit('done', { run_id: 'run-1', status: 'failed' }));

    expect(screen.getByText('terminal')).toBeInTheDocument();
    expect(source.close).toHaveBeenCalled();
  });
});
