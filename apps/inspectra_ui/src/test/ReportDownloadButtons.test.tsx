import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ReportDownloadButtons } from '../components/reports/ReportDownloadButtons';
import { WorkspaceModeProvider } from '../state/WorkspaceModeContext';


function renderDownloads(mode: 'real' | 'demo' = 'real') {
  return render(
    <MemoryRouter initialEntries={[mode === 'demo' ? '/demo/runs/run-1' : '/runs/run-1']}>
      <WorkspaceModeProvider mode={mode}>
        <ReportDownloadButtons runId="run-1" />
      </WorkspaceModeProvider>
    </MemoryRouter>,
  );
}


describe('ReportDownloadButtons', () => {
  afterEach(() => vi.restoreAllMocks());

  it('offers all four on-demand formats and downloads with meaningful names', () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    renderDownloads();

    const html = screen.getByRole('button', { name: 'Download HTML' });
    expect(screen.getByRole('button', { name: 'Download PDF' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Download JUnit' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Download SARIF' })).toBeEnabled();

    fireEvent.click(html);

    expect(click).toHaveBeenCalledOnce();
    const clickedAnchor = click.mock.contexts[0] as HTMLAnchorElement;
    expect(clickedAnchor?.getAttribute('href')).toBe('/api/runs/run-1/report?format=html');
    expect(clickedAnchor?.download).toBe('inspectra-run-run-1.html');
  });

  it('keeps demo exports visibly disabled', () => {
    renderDownloads('demo');

    for (const name of ['Download HTML', 'Download PDF', 'Download JUnit', 'Download SARIF']) {
      const button = screen.getByRole('button', { name });
      expect(button).toBeDisabled();
      expect(button).toHaveAttribute(
        'title',
        'Available in your real workspace. Leave demo to get started.',
      );
    }
  });
});
