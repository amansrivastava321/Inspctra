# Task-Oriented Sidebar Design

**Date:** 2026-08-14

## Goal

Replace Inspectra's flat navigation with four task-oriented, collapsible groups while preserving all current pages and the real/demo workspace boundary.

## Navigation model

The sidebar is driven by one typed configuration rather than repeated JSX. Each item declares its label, destination, icon, active-route matcher, and optional Preview state.

- **Setup:** Projects (`/projects`), Apps (`/projects?view=apps`), Connect App (`/projects/new`)
- **Test:** Validation Packs (`/packs`), Live Runs (`/runs`), Manual Tests (`/runs?mode=manual`)
- **Investigate:** Evidence Center (`/evidence`), Reports (`/reports`), Runtime Doctor (`/runtime-doctor`)
- **Configure:** Models (`/models`), Settings (`/settings`), Integrations (`/connectors`, Preview)

The query strings disambiguate sidebar state for destinations that share a page without changing React Router paths. `/doctor` remains valid and `/runtime-doctor` is added as an alias. Dashboard remains at `/` and is opened by the Inspectra logo. Memory remains routable at `/memory` but leaves primary navigation.

## Interaction and persistence

Group headers are buttons with icons, labels, chevrons, `aria-expanded`, and `aria-controls`. Setup and Test default open when no stored preference exists; Investigate and Configure default closed. The complete state is stored under a versioned localStorage key. Route changes open the group containing the active page, including direct deep links.

The active item uses an accent-tinted background and left accent border. Exact matchers prevent both items that share a pathname from highlighting simultaneously.

## Quick actions

`+ New Pack` navigates to `/packs/new` and is disabled in demo mode. `Run All` is present but disabled with an explanatory tooltip because scheduled and bulk execution have no wired endpoint and scheduling is currently Preview. It is also disabled in demo mode.

## Shell visibility

`AppShell` owns a sidebar-visible boolean and passes an accessible hamburger control into `Topbar`. The control hides or restores the whole sidebar without changing content layout or routes. Responsive breakpoints remain Phase 4 scope.

## Manual runs view

`LiveRunsPage` recognizes `?mode=manual`, changes its heading, and filters loaded runs to `execution_mode === "manual"`. This makes the Manual Tests navigation item meaningful while keeping `/runs` as the route.

## Testing

Component tests cover default groups, toggling, persistence, active/deep-route expansion, duplicate-route disambiguation, Preview labeling, quick actions, demo disabling, and shell visibility. The existing full frontend suite and production TypeScript/Vite build remain required.

