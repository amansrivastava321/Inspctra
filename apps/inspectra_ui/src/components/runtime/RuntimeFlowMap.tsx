import { P, F } from '../../design/tokens';

const NODES = [
  { id: 'engine',   label: 'Inspectra\nEngine',  x: 0,   y: 50 },
  { id: 'driver',   label: 'UI Driver',           x: 130, y: 50 },
  { id: 'app',      label: 'App Screen',          x: 260, y: 50 },
  { id: 'backend',  label: 'Backend',             x: 390, y: 50 },
  { id: 'db',       label: 'Database',            x: 520, y: 50 },
  { id: 'logs',     label: 'Logs',                x: 390, y: 130 },
  { id: 'ai',       label: 'AI Model',            x: 260, y: 130 },
  { id: 'evidence', label: 'Evidence',            x: 130, y: 130 },
  { id: 'verdict',  label: 'Verdict',             x: 0,   y: 130 },
] as const;

const EDGES: [string, string][] = [
  ['engine','driver'],['driver','app'],['app','backend'],['backend','db'],
  ['backend','logs'],['app','ai'],['ai','evidence'],['evidence','verdict'],
];

type NodeId = typeof NODES[number]['id'];

interface RuntimeFlowMapProps {
  activeNode?: string;
  compact?: boolean;
}

export function RuntimeFlowMap({ activeNode, compact }: RuntimeFlowMapProps) {
  const W = compact ? 480 : 640;
  const scale = compact ? 0.75 : 1;

  return (
    <div style={{ overflow: 'hidden', borderRadius: 8 }}>
      <svg
        viewBox="0 -10 640 200"
        style={{ width: '100%', height: compact ? 100 : 130, display: 'block' }}
        aria-label="Runtime flow map"
      >
        {/* Edges */}
        {EDGES.map(([a, b]) => {
          const na = NODES.find(n => n.id === a)!;
          const nb = NODES.find(n => n.id === b)!;
          const active = activeNode === a || activeNode === b;
          return (
            <line key={`${a}-${b}`}
              x1={na.x + 44} y1={na.y + 18} x2={nb.x + 44} y2={nb.y + 18}
              stroke={active ? P.accent : P.border}
              strokeWidth={active ? 1.5 : 1}
              strokeDasharray={active ? undefined : '3 3'}
            />
          );
        })}

        {/* Nodes */}
        {NODES.map(({ id, label, x, y }) => {
          const active = activeNode === id;
          return (
            <g key={id} transform={`translate(${x}, ${y})`}>
              <rect
                width={88} height={36} rx={7}
                fill={active ? P.accentSoft : P.cardHi}
                stroke={active ? P.accent : P.border}
                strokeWidth={active ? 1.5 : 1}
              />
              {active && (
                <rect width={88} height={36} rx={7}
                  fill="none" stroke={P.accent} strokeWidth={2.5} opacity={0.3} />
              )}
              <text
                x={44} y={label.includes('\n') ? 13 : 22}
                textAnchor="middle"
                fontSize={9}
                fill={active ? P.accent : P.textDim}
                fontFamily={F.mono}
                style={{ userSelect: 'none' }}
              >
                {label.split('\n').map((line, i) => (
                  <tspan key={i} x={44} dy={i === 0 ? 0 : 11}>{line}</tspan>
                ))}
              </text>
              {active && (
                <circle cx={84} cy={4} r={4} fill={P.accent}>
                  <animate attributeName="opacity" values="1;0.3;1" dur="1s" repeatCount="indefinite" />
                </circle>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
