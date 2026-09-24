import { useParams } from 'react-router-dom';
import LiveRunDetailWorkspace from './LiveRunDetailWorkspace';

export default function LiveRunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  // Historical citations reuse this route; selection and evidence state belong to one run.
  return <LiveRunDetailWorkspace key={runId} />;
}

export { SecurityFindingsCard, toDisplaySteps } from './LiveRunDetailWorkspace';
