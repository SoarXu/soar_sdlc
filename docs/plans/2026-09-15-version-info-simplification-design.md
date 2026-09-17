# Version Information Simplification Design

The system information dialog serves users checking whether the frontend and backend run the same release version. It shows frontend version, backend version, and their comparison status. A failed version request is described as version information unavailable, not as a failed backend service.

`GET /api/v1/version` returns only `app_version` and `environment`. It has no database dependency and does not report the Alembic revision or Git commit. The frontend comparison uses version numbers only. Existing package `VERSION`, `release.env`, Docker build arguments, and production build metadata validation remain unchanged so operators can trace a release to its source commit outside the application.

Backend and frontend contract tests cover the reduced response, a version request without a database dependency, the three-row dialog, and version-only status comparison. No database migration is required.
