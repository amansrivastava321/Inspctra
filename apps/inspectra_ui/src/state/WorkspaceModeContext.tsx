import { createContext, useCallback, useContext, useMemo } from 'react';
import type { ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import type { NavigateFunction, NavigateOptions, To } from 'react-router-dom';
import { generateDemoWorkspace } from '../mocks/sampleData';
import type { DemoWorkspace } from '../mocks/sampleData';
export { DEMO_READ_ONLY_TOOLTIP } from './workspaceMode';

export type WorkspaceMode = 'real' | 'demo';

interface WorkspaceModeValue {
  mode: WorkspaceMode;
  isDemo: boolean;
  demoWorkspace: DemoWorkspace | null;
  toWorkspacePath: (path: string) => string;
  realWorkspacePath: string;
}

const REAL_WORKSPACE: WorkspaceModeValue = {
  mode: 'real',
  isDemo: false,
  demoWorkspace: null,
  toWorkspacePath: path => path,
  realWorkspacePath: '/',
};

const WorkspaceModeContext = createContext<WorkspaceModeValue>(REAL_WORKSPACE);

export function WorkspaceModeProvider({ mode, children }: { mode: WorkspaceMode; children: ReactNode }) {
  const { pathname, search } = useLocation();
  const demoWorkspace = useMemo(() => mode === 'demo' ? generateDemoWorkspace() : null, [mode]);
  const toWorkspacePath = useCallback((path: string) => {
    if (mode === 'real') return path;
    if (path === '/' || path === '') return '/demo';
    return `/demo${path.startsWith('/') ? path : `/${path}`}`;
  }, [mode]);
  const realWorkspacePathname = mode === 'demo'
    ? pathname.replace(/^\/demo(?=\/|$)/, '') || '/'
    : pathname;
  const realWorkspacePath = `${realWorkspacePathname}${search}`;

  const value = useMemo<WorkspaceModeValue>(() => ({
    mode,
    isDemo: mode === 'demo',
    demoWorkspace,
    toWorkspacePath,
    realWorkspacePath,
  }), [demoWorkspace, mode, realWorkspacePath, toWorkspacePath]);

  return <WorkspaceModeContext.Provider value={value}>{children}</WorkspaceModeContext.Provider>;
}

export function useWorkspaceMode() {
  return useContext(WorkspaceModeContext);
}

/** Navigate within the active workspace, preserving the /demo prefix. */
export function useWorkspaceNavigate(): NavigateFunction {
  const navigate = useNavigate();
  const { toWorkspacePath } = useWorkspaceMode();
  return useCallback(((to: To | number, options?: NavigateOptions) => {
    if (typeof to === 'number') return navigate(to);
    const target = typeof to === 'string' && to.startsWith('/') ? toWorkspacePath(to) : to;
    return options === undefined ? navigate(target) : navigate(target, options);
  }) as NavigateFunction, [navigate, toWorkspacePath]);
}
