import { Download } from 'lucide-react';
import { Btn } from '../layout/AppShell';
import {
  runReportDownloadUrl,
  runReportFilename,
  type RunReportFormat,
} from '../../api/client';
import { DEMO_READ_ONLY_TOOLTIP, useWorkspaceMode } from '../../state/WorkspaceModeContext';


const FORMATS: Array<{ format: RunReportFormat; label: string }> = [
  { format: 'html', label: 'HTML' },
  { format: 'pdf', label: 'PDF' },
  { format: 'junit', label: 'JUnit' },
  { format: 'sarif', label: 'SARIF' },
];


export function ReportDownloadButtons({
  runId,
  compact = false,
}: {
  runId: string;
  compact?: boolean;
}) {
  const { isDemo } = useWorkspaceMode();

  const download = (format: RunReportFormat) => {
    const anchor = document.createElement('a');
    anchor.href = runReportDownloadUrl(runId, format);
    anchor.download = runReportFilename(runId, format);
    anchor.rel = 'noopener noreferrer';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  };

  return (
    <div
      aria-label="Report downloads"
      onClick={event => event.stopPropagation()}
      style={{ display: 'inline-flex', alignItems: 'center', gap: 5, flexWrap: 'wrap' }}
    >
      {FORMATS.map(({ format, label }) => (
        <Btn
          key={format}
          size="sm"
          variant="secondary"
          aria-label={`Download ${label}`}
          disabled={isDemo}
          title={isDemo ? DEMO_READ_ONLY_TOOLTIP : `Download ${label} report`}
          onClick={() => download(format)}
          style={compact ? { padding: '4px 7px', fontSize: 11 } : undefined}
        >
          <Download size={compact ? 10 : 12} />{label}
        </Btn>
      ))}
    </div>
  );
}
