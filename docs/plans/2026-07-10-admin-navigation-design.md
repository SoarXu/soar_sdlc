# Admin Navigation Design

## Goal

Group `角色管理` and `工作流配置` under a new `后台管理` navigation entry, and provide a lightweight overview page at `/admin` so the backend-related capabilities live under one clear entry point.

## Navigation Design

- Add a new top-level navigation group labeled `后台管理`.
- Keep the existing `角色管理` and `工作流配置` pages and routes so direct access and old bookmarks continue to work.
- Add a new overview route at `/admin`.
- The sidebar should expose:
  - `后台管理` as the parent entry.
  - `角色管理` as a child entry.
  - `工作流配置` as a child entry.

## Overview Page

The new `/admin` page should act as a module index rather than a dashboard.

- Reuse the existing `.page-head` page structure.
- Show a concise title and subtitle.
- Render two compact module entry cards:
  - `角色管理`
  - `工作流配置`
- Each card should include:
  - module name
  - one-line description
  - clear entry action

The layout should be compact and expandable:

- Use a responsive grid based on `repeat(auto-fit, minmax(240px, 1fr))`.
- Limit the content width so two cards do not stretch awkwardly on wide screens.
- Collapse to a single column on smaller screens.

## Implementation Scope

- Modify the frontend sidebar menu structure in `frontend/src/layout/MainLayout.vue`.
- Add the `/admin` route in `frontend/src/router/index.js`.
- Create a new overview page in `frontend/src/views/AdminView.vue`.
- Add small supporting styles in `frontend/src/styles.css`.

No backend API or data model changes are required.

## Interaction Details

- Visiting `/admin` shows the backend overview page.
- Visiting `/roles` or `/workflow` still opens the existing pages.
- The sidebar should keep the `后台管理` group visibly associated with both child pages.
- The overview cards should navigate via router links or button actions without introducing a new state container.

## Testing

- Frontend build must succeed after the navigation changes.
- Manual verification should confirm:
  - sidebar renders the new backend group
  - `/admin` loads correctly
  - overview cards navigate to `/roles` and `/workflow`
  - `/roles` and `/workflow` remain directly reachable
  - desktop and narrow layouts do not overflow
