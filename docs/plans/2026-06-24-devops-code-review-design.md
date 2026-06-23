# DevOps Code Review Design

## Scope

DevOps adds GitLab/Jenkins integration foundations and code review work items:

- GitLab repositories and Jenkins jobs can be registered.
- GitLab commit webhook payloads can be received through backend APIs.
- Commit messages are parsed for platform object references:
  - `REQ-<id>` or `requirement#<id>`
  - `TASK-<id>` or `task#<id>`
  - `BUG-<id>` or `bug#<id>`
- Matched commits are shown on requirement, task, and bug detail pages.
- Clicking a commit opens a diff review dialog with file-by-file before/after patch content.
- Each received commit creates a code review item for the workbench.

## First Implementation Contract

GitLab/Jenkins credentials are configuration records only in this iteration. Commit ingestion uses a GitLab-compatible webhook/manual payload endpoint, so local testing does not require external GitLab access.

Code review workbench items are read-only tasks in this iteration. They link to the DevOps review dialog and can be marked reviewed through the DevOps API.
