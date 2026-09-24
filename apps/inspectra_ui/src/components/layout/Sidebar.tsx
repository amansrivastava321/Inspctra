import { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import type { LucideIcon } from 'lucide-react';
import {
  AppWindow,
  Camera,
  ChevronDown,
  ChevronRight,
  CirclePlus,
  ClipboardCheck,
  Cpu,
  FileText,
  FlaskConical,
  FolderCog,
  FolderOpen,
  Gauge,
  Package,
  Play,
  Plug,
  Search,
  Settings,
  SlidersHorizontal,
  Stethoscope,
  User,
} from 'lucide-react';
import { P, F } from '../../design/tokens';
import { ReadinessScore } from '../status/ReadinessScore';
import { PreviewBadge } from '../PreviewBadge';
import { useApi } from '../../hooks/useApi';
import { get } from '../../api/client';
import type { Project } from '../../types/api';
import {
  DEMO_READ_ONLY_TOOLTIP,
  useWorkspaceMode,
} from '../../state/WorkspaceModeContext';

type GroupId = 'setup' | 'test' | 'investigate' | 'configure';

interface WorkspaceLocation {
  pathname: string;
  search: string;
}

interface NavigationItem {
  label: string;
  destination: string;
  Icon: LucideIcon;
  preview?: boolean;
  matches: (location: WorkspaceLocation) => boolean;
}

interface NavigationGroup {
  id: GroupId;
  label: string;
  Icon: LucideIcon;
  items: NavigationItem[];
}

type GroupState = Record<GroupId, boolean>;

const GROUP_STORAGE_KEY = 'inspectra.sidebar.groups.v1';
const DEFAULT_GROUP_STATE: GroupState = {
  setup: true,
  test: true,
  investigate: false,
  configure: false,
};

const queryValue = (location: WorkspaceLocation, key: string) =>
  new URLSearchParams(location.search).get(key);

const pathStartsWith = (pathname: string, base: string) =>
  pathname === base || pathname.startsWith(`${base}/`);

export const NAV_GROUPS: NavigationGroup[] = [
  {
    id: 'setup',
    label: 'Setup',
    Icon: FolderCog,
    items: [
      {
        label: 'Projects',
        destination: '/projects',
        Icon: FolderOpen,
        matches: ({ pathname, search }) => pathname === '/projects' && queryValue({ pathname, search }, 'view') !== 'apps',
      },
      {
        label: 'Apps',
        destination: '/projects?view=apps',
        Icon: AppWindow,
        matches: location => (
          (location.pathname === '/projects' && queryValue(location, 'view') === 'apps')
          || pathStartsWith(location.pathname, '/apps')
        ),
      },
      {
        label: 'Connect App',
        destination: '/projects/new',
        Icon: CirclePlus,
        matches: ({ pathname }) => pathname === '/projects/new',
      },
    ],
  },
  {
    id: 'test',
    label: 'Test',
    Icon: FlaskConical,
    items: [
      {
        label: 'Validation Packs',
        destination: '/packs',
        Icon: Package,
        matches: ({ pathname }) => pathStartsWith(pathname, '/packs'),
      },
      {
        label: 'Live Runs',
        destination: '/runs',
        Icon: Play,
        matches: location => pathStartsWith(location.pathname, '/runs') && queryValue(location, 'mode') !== 'manual',
      },
      {
        label: 'Manual Tests',
        destination: '/runs?mode=manual',
        Icon: ClipboardCheck,
        matches: location => location.pathname === '/runs' && queryValue(location, 'mode') === 'manual',
      },
    ],
  },
  {
    id: 'investigate',
    label: 'Investigate',
    Icon: Search,
    items: [
      {
        label: 'Evidence Center',
        destination: '/evidence',
        Icon: Camera,
        matches: ({ pathname }) => pathStartsWith(pathname, '/evidence'),
      },
      {
        label: 'Reports',
        destination: '/reports',
        Icon: FileText,
        matches: ({ pathname }) => pathStartsWith(pathname, '/reports'),
      },
      {
        label: 'Runtime Doctor',
        destination: '/runtime-doctor',
        Icon: Stethoscope,
        matches: ({ pathname }) => pathname === '/runtime-doctor' || pathname === '/doctor',
      },
    ],
  },
  {
    id: 'configure',
    label: 'Configure',
    Icon: SlidersHorizontal,
    items: [
      {
        label: 'Models',
        destination: '/models',
        Icon: Cpu,
        matches: ({ pathname }) => pathname === '/models' || pathname === '/model-settings',
      },
      {
        label: 'Settings',
        destination: '/settings',
        Icon: Settings,
        matches: ({ pathname }) => pathStartsWith(pathname, '/settings'),
      },
      {
        label: 'Integrations',
        destination: '/connectors',
        Icon: Plug,
        preview: true,
        matches: ({ pathname }) => pathStartsWith(pathname, '/connectors'),
      },
    ],
  },
];

interface SidebarProps {
  /** Pass readiness score from Runtime Doctor API. Undefined = no data. */
  readinessScore?: number;
  readinessSubtitle?: string;
  /** Called after nav item click — used on mobile to close the overlay. */
  onClose?: () => void;
}

function getProjects() {
  return get<Project[]>('/projects');
}

function readStoredGroupState(): GroupState {
  try {
    const raw = localStorage.getItem(GROUP_STORAGE_KEY);
    if (!raw) return DEFAULT_GROUP_STATE;
    const value = JSON.parse(raw) as Partial<GroupState>;
    return {
      setup: typeof value.setup === 'boolean' ? value.setup : DEFAULT_GROUP_STATE.setup,
      test: typeof value.test === 'boolean' ? value.test : DEFAULT_GROUP_STATE.test,
      investigate: typeof value.investigate === 'boolean' ? value.investigate : DEFAULT_GROUP_STATE.investigate,
      configure: typeof value.configure === 'boolean' ? value.configure : DEFAULT_GROUP_STATE.configure,
    };
  } catch {
    return DEFAULT_GROUP_STATE;
  }
}

export function Sidebar({ readinessScore, readinessSubtitle, onClose }: SidebarProps) {
  const { pathname, search } = useLocation();
  const navigate = useNavigate();
  const { isDemo, toWorkspacePath } = useWorkspaceMode();
  const { data: projects, isOffline } = useApi(useCallback(getProjects, []), {
    demo: workspace => workspace.projects,
  });
  const [openGroups, setOpenGroups] = useState<GroupState>(readStoredGroupState);

  const workspacePathname = isDemo
    ? pathname.replace(/^\/demo(?=\/|$)/, '') || '/'
    : pathname;
  const workspaceLocation = { pathname: workspacePathname, search };
  const activeGroup = NAV_GROUPS.find(group =>
    group.items.some(item => item.matches(workspaceLocation)),
  )?.id;

  useEffect(() => {
    if (!activeGroup) return;
    setOpenGroups(current => current[activeGroup]
      ? current
      : { ...current, [activeGroup]: true });
  }, [activeGroup, pathname, search]);

  useEffect(() => {
    try {
      localStorage.setItem(GROUP_STORAGE_KEY, JSON.stringify(openGroups));
    } catch {
      // Navigation remains usable when storage is blocked or full.
    }
  }, [openGroups]);

  const workspaceLabel = (() => {
    if (isOffline) return 'Backend offline';
    if (!projects || !Array.isArray(projects)) return '—';
    if (projects.length === 0) return 'No project selected';
    if (projects.length === 1) return projects[0]?.name ?? '—';
    return `${projects[0]?.name ?? '—'} (+${projects.length - 1} more)`;
  })();

  const go = (destination: string) => {
    navigate(toWorkspacePath(destination));
    onClose?.();
  };
  const bulkRunTooltip = 'Bulk execution is unavailable until scheduling is enabled.';

  return (
    <aside style={{
      width: 232,
      flexShrink: 0,
      height: '100%',
      background: P.surface,
      borderRight: `1px solid ${P.border}`,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }}>
      <div style={{ padding: '14px 12px 12px', borderBottom: `1px solid ${P.border}` }}>
        <button
          type="button"
          data-demo-allowed
          aria-label="Inspectra dashboard"
          onClick={() => go('/')}
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginBottom: 10,
            padding: 0,
            border: 0,
            background: 'transparent',
            color: P.text,
            cursor: 'pointer',
            textAlign: 'left',
          }}
        >
          <span style={{
            width: 26,
            height: 26,
            borderRadius: 7,
            background: `linear-gradient(135deg, ${P.accent}, #7c6fff)`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 13,
            fontWeight: 700,
            color: '#fff',
            flexShrink: 0,
          }}>i</span>
          <span style={{ fontSize: 14, fontWeight: 600 }}>Inspectra</span>
        </button>

        <button
          type="button"
          data-demo-allowed
          onClick={() => go('/projects')}
          title={projects?.length === 0 ? 'No projects yet — click to create one' : `Switch project (${workspaceLabel})`}
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '5px 8px',
            borderRadius: 6,
            background: P.cardHi,
            border: `1px solid ${P.border}`,
            cursor: 'pointer',
          }}
        >
          <span style={{
            fontSize: 11,
            fontFamily: F.mono,
            color: projects?.length === 0 ? P.textFaint : P.textMute,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            maxWidth: 142,
          }}>
            {workspaceLabel}
          </span>
          <ChevronDown size={12} color={P.textMute} style={{ flexShrink: 0 }} />
        </button>
      </div>

      <nav aria-label="Primary navigation" style={{ flex: 1, overflowY: 'auto', padding: '10px 8px' }}>
        <section aria-label="Quick Actions" style={{ marginBottom: 10 }}>
          <div style={{
            padding: '0 7px 5px',
            fontSize: 9,
            color: P.textFaint,
            fontFamily: F.mono,
            textTransform: 'uppercase',
            letterSpacing: '0.09em',
          }}>
            Quick Actions
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 5 }}>
            <button
              type="button"
              disabled={isDemo}
              title={isDemo ? DEMO_READ_ONLY_TOOLTIP : 'Create a validation pack'}
              onClick={() => go('/packs/new')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 5,
                padding: '6px 7px',
                borderRadius: 6,
                border: `1px solid ${P.accent}55`,
                background: P.accentSoft,
                color: P.accent,
                cursor: isDemo ? 'not-allowed' : 'pointer',
                opacity: isDemo ? 0.5 : 1,
                fontSize: 11,
                fontWeight: 600,
              }}
            >
              <CirclePlus size={12} />New Pack
            </button>
            <button
              type="button"
              disabled
              title={isDemo ? DEMO_READ_ONLY_TOOLTIP : bulkRunTooltip}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 5,
                padding: '6px 7px',
                borderRadius: 6,
                border: `1px solid ${P.border}`,
                background: P.cardHi,
                color: P.textMute,
                cursor: 'not-allowed',
                opacity: 0.55,
                fontSize: 11,
                fontWeight: 600,
              }}
            >
              <Gauge size={12} />Run All
            </button>
          </div>
        </section>

        {NAV_GROUPS.map(group => {
          const expanded = openGroups[group.id];
          const panelId = `sidebar-group-${group.id}`;
          const GroupIcon = group.Icon;
          return (
            <section key={group.id} style={{ marginBottom: 5 }}>
              <button
                type="button"
                data-demo-allowed
                aria-expanded={expanded}
                aria-controls={panelId}
                onClick={() => setOpenGroups(current => ({
                  ...current,
                  [group.id]: !current[group.id],
                }))}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 7,
                  padding: '6px 8px',
                  borderRadius: 6,
                  border: 0,
                  background: 'transparent',
                  color: P.textMute,
                  cursor: 'pointer',
                  textAlign: 'left',
                  fontSize: 10,
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.07em',
                }}
              >
                <GroupIcon size={13} strokeWidth={1.8} aria-hidden="true" />
                <span>{group.label}</span>
                {expanded
                  ? <ChevronDown size={12} style={{ marginLeft: 'auto' }} aria-hidden="true" />
                  : <ChevronRight size={12} style={{ marginLeft: 'auto' }} aria-hidden="true" />}
              </button>

              <div id={panelId} hidden={!expanded} style={{ marginTop: 1 }}>
                  {group.items.map(item => {
                    const active = item.matches(workspaceLocation);
                    const ItemIcon = item.Icon;
                    return (
                      <button
                        type="button"
                        data-demo-allowed
                        key={`${group.id}-${item.label}`}
                        className="sidebar-nav-item"
                        aria-current={active ? 'page' : undefined}
                        onClick={() => go(item.destination)}
                        style={{
                          width: '100%',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          padding: '7px 8px 7px 11px',
                          borderRadius: 6,
                          marginBottom: 1,
                          border: 'none',
                          borderLeft: `2px solid ${active ? P.accent : 'transparent'}`,
                          background: active ? P.accentSoft : 'transparent',
                          color: active ? P.accent : P.textDim,
                          cursor: 'pointer',
                          textAlign: 'left',
                          fontSize: 12,
                          fontWeight: active ? 600 : 400,
                          transition: 'background 0.12s, color 0.12s',
                        }}
                        onMouseEnter={event => {
                          if (!active) event.currentTarget.style.background = P.cardHi;
                        }}
                        onMouseLeave={event => {
                          if (!active) event.currentTarget.style.background = 'transparent';
                        }}
                      >
                        <ItemIcon size={14} strokeWidth={active ? 2 : 1.6} aria-hidden="true" />
                        <span>{item.label}</span>
                        {item.preview && <PreviewBadge style={{ marginLeft: 'auto' }} />}
                      </button>
                    );
                  })}
              </div>
            </section>
          );
        })}
      </nav>

      <div style={{ borderTop: `1px solid ${P.border}`, background: P.card }}>
        <ReadinessScore score={readinessScore} subtitle={readinessSubtitle} compact />
      </div>

      <div style={{
        borderTop: `1px solid ${P.border}`,
        padding: '9px 12px',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}>
        <div style={{
          width: 28,
          height: 28,
          borderRadius: 99,
          flexShrink: 0,
          background: P.cardHi,
          border: `1px solid ${P.border}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          <User size={14} color={P.textMute} />
        </div>
        <span style={{ fontSize: 12, color: P.textDim, fontWeight: 500 }}>Local user</span>
      </div>

      {!isDemo && (
        <button onClick={() => navigate('/demo')} style={{
          margin: '0 12px 12px',
          padding: '7px 10px',
          borderRadius: 7,
          border: '1px solid #6366f166',
          background: '#312e8133',
          color: '#a5b4fc',
          cursor: 'pointer',
          fontSize: 12,
          fontWeight: 600,
        }}>Try Demo</button>
      )}
    </aside>
  );
}
