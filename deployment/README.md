# Release 1.0.0 deployment

This template upgrades an existing MySQL database. It does not carry database files or reset business records. The package's `VERSION` identifies the release; generated `deployment/release.env` supplies the immutable version and source commit to both Docker builds.

1. Back up the existing MySQL database and preserve the existing Compose project, `.env`, and `db_data` volume. Set `COMPOSE_PROJECT_NAME` in `.env` to the old project's actual name (check the old Compose project/volume before the upgrade); the template refuses to start without it.
2. Replace the application files in the existing deployment directory. Never run `docker compose down -v` or a reset/bootstrap command during an upgrade.
3. From `deployment/`, run `docker compose --env-file .env --env-file release.env up -d --build`.
4. The backend runs `alembic upgrade head` before starting the API. Verify `docker compose --env-file .env --env-file release.env exec backend alembic current`.
5. Compare `VERSION` and `release.env` to `curl http://SERVER/api/v1/version`; then open the sidebar system information and compare frontend and backend versions and commits.

For a new empty database, complete the foundation-data initialization process separately before starting this upgrade template. `.env` is operator-owned and must never be added to the package.
