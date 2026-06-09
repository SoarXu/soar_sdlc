# API-Backed Frontend Design

## Goal

All PRD-visible frontend features must use backend APIs and persist business data to MySQL. Static HTML prototypes and in-memory page data are not valid implementations for CRUD or workflow behavior.

## Architecture

The backend remains the source of truth. FastAPI controllers expose `/api/v1/*` endpoints, services enforce PRD business rules, SQLAlchemy models map to the MySQL data dictionary, and Vue pages call those endpoints through `frontend/src/api/*` modules.

The frontend may keep transient UI state such as dialog visibility and form drafts, but lists, dashboard metrics, create/update/delete actions, workflow actions, and status transitions must come from backend responses.

## Rules

- Do not build business interaction in `project-management-prototype.html`.
- Do not use static arrays for PRD module data in Vue pages.
- Do not create frontend-only CRUD.
- Do not invent fields that are absent from the PRD/data dictionary.
- Add backend tests before backend behavior changes.
- Verify with MySQL-backed API calls before marking a feature complete.
- Commit each completed code update.

## Initial Implementation Slice

1. Add backend CRUD APIs for project sets and complete project CRUD.
2. Add backend dashboard summary API from database counts.
3. Replace visible frontend static data with API calls:
   - Dashboard summary
   - Project set list/create/update/delete
   - Project list/create/update/delete
4. Keep later PRD modules behind real APIs as they are implemented.
