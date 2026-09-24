import { beforeEach, describe, expect, it, vi } from 'vitest';
import { checkHealth, get, post } from '../api/client';

describe('demo API isolation', () => {
  beforeEach(() => {
    vi.mocked(fetch).mockClear();
    window.history.pushState({}, '', '/demo/projects');
  });

  it('never sends reads to the backend from demo routes', async () => {
    await expect(get('/projects')).rejects.toThrow(/read-only demo workspace/i);
    expect(fetch).not.toHaveBeenCalled();
  });

  it('never sends mutations to the backend from demo routes', async () => {
    await expect(post('/projects', { name: 'Not real' })).rejects.toThrow(/read-only demo workspace/i);
    expect(fetch).not.toHaveBeenCalled();
  });

  it('does not probe backend health from demo routes', async () => {
    await expect(checkHealth()).resolves.toBe('offline');
    expect(fetch).not.toHaveBeenCalled();
  });

  it('treats a dev-proxy 5xx health response as offline', async () => {
    window.history.pushState({}, '', '/');
    vi.mocked(fetch).mockResolvedValue({ ok: false, status: 500 } as Response);

    await expect(checkHealth()).resolves.toBe('offline');
  });
});
