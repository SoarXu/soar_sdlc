# Gitea Pull Request Review Design

## Goal

Make Gitea the authoritative source for repositories and pull requests while
allowing reviewers to complete pull request review from the SDLC DevOps module.
SDLC must synchronize Gitea pull request state, assign and track review work,
publish inline comments, and submit approval or change-request decisions back
to Gitea.

## Scope

The first release supports one Gitea connection and one or more configured
repositories. It synchronizes pull request lifecycle events, shows pull
request diffs in SDLC, creates inline review comments, and records approval or
change-request decisions in both systems.

The first release does not configure Gitea branch-protection rules or block
merges. Those rules can be enabled after the synchronization and review flow
has been verified in production-like deployment.

## Architecture

Gitea remains the external system of record for Git repositories, pull request
metadata, source diffs, review comments, and review decisions. SDLC stores the
external identity and a local projection for task assignment, links to SDLC
requirements/tasks/bugs, audit history, and retryable outbound operations.

The SDLC backend receives Gitea webhooks for pull request and issue-comment
events. It validates a configured webhook secret, applies the event
idempotently, and refreshes the affected pull request from the Gitea REST API.
The frontend reads only SDLC APIs. When a reviewer comments or decides in
SDLC, the backend persists an outbound operation, calls Gitea, then refreshes
the local projection. A failed remote call is visible as a retryable failure;
the UI must not present it as completed.

## Data Model

Extend `DevopsRepository` so a repository is tied to a Git platform connection
and has the Gitea owner/name identity required for API requests. Retain
`repository_url`, `default_branch`, and the existing soft-delete behavior.

Create these entities:

- `DevopsPullRequest`: repository, Gitea pull request number and node ID,
  title/body, state, draft flag, source and target branches, head/base SHAs,
  author metadata, web URL, Gitea timestamps, and last synchronization time.
- `DevopsPullRequestLink`: links a pull request to SDLC requirement, task, or
  bug records inferred from title/body/commit messages or added explicitly.
- `DevopsPullRequestReview`: reviewer, decision (`approved` or
  `request_changes`), body, Gitea review ID, status, and timestamps.
- `DevopsPullRequestComment`: review reference, file path, new-side line,
  original commit SHA, body, Gitea comment ID, status, and timestamps.
- `DevopsGiteaWebhookDelivery`: delivery identifier, event type, repository,
  payload fingerprint, processing status, failure text, and receive time.
- `DevopsGiteaOutboundOperation`: intent, target pull request, request body,
  remote response details, status, retry count, and error text.

The unique external identity for a pull request is `(repository_id,
external_number)`. Webhook deliveries and outbound remote IDs are unique where
Gitea provides stable identifiers.

## API Integration

The Gitea adapter uses an encrypted platform access token and sends it as
`Authorization: token <token>`. It wraps the Gitea REST API so controller and
service code have no provider-specific HTTP logic.

Required adapter operations are:

- list repositories available to the configured account;
- fetch a pull request and its commits/files;
- fetch existing pull request comments and reviews;
- create a pull request comment with file, line, side, and commit context;
- submit a pull request review decision;
- optionally re-request the current pull request representation after every
  successful write.

The webhook endpoint is unauthenticated at the HTTP application level but
requires a constant-time comparison of the configured Gitea webhook secret.
It accepts only supported events and logs malformed or unauthorized requests
without changing review state.

## User Experience

The DevOps module replaces commit-level review as the primary review surface:

- Repository configuration selects a verified Gitea connection and records
  owner/repository identity.
- A `Pull Requests` list shows title/number, status, branches, author,
  assigned reviewer, review decision, linked SDLC objects, and latest build.
- `My Reviews` filters to pull requests assigned to the current user and still
  requiring action.
- The detail view renders the Gitea diff by file and hunk, supports line
  selection, existing comment threads, an inline comment composer, and review
  actions: approve or request changes.
- A retry action is available only for the current user's failed outbound
  comments or decisions; synchronization failures are visible to authorized
  administrators.

Existing Commit and Jenkins screens remain available for audit/history during
the migration. Pull request detail links to the source PR in Gitea.

## State and Error Handling

Inbound webhook processing must be idempotent. Re-delivered events either
produce no change or refresh the same local pull request. A Gitea API failure
during inbound processing records the delivery as failed and does not erase the
previous valid local state.

Outbound review actions transition through `pending`, `succeeded`, or `failed`.
The local review/comment is associated with the operation. A failed action is
not counted as approved or commented until Gitea accepts it. Retry uses the
stored intent with the caller re-authorized before the remote call.

## Local Demonstration Deployment

For the local proof of concept, configure the Gitea connection with
`http://localhost:3002` and a personal access token with repository and pull
request write permission. Run SDLC backend on port 8000 and frontend on port
5173.

If both processes run directly on Windows, configure the Gitea webhook target
as `http://127.0.0.1:8000/api/v1/devops/gitea/webhook/<repository-id>`. If
Gitea runs in a container or the services move to separate hosts, use the
backend's network-reachable address instead. The webhook secret must match the
repository configuration in SDLC.

## Verification

Automated tests cover webhook authentication/idempotency, pull request
synchronization, explicit and inferred SDLC links, inline-comment payload
construction, review-decision payloads, remote API failure persistence, and
authorization. Browser verification covers repository setup, a webhook-created
pull request, an inline comment, an approval or change request, and visible
failure/retry state. A manual Gitea check confirms the comment and decision
appear on the original pull request.
