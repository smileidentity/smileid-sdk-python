# Agent notes

This repository holds Smile ID's V3 server-side SDK for Python (package name `smile-identity-core`, importable module `smileid`).

## Source of truth

The API surface (endpoints, request and response shapes) is defined by the OpenAPI specs at [smileidentity/api-reference](https://github.com/smileidentity/api-reference). Treat that repository as authoritative when generating or reviewing client code — do not invent endpoints or fields that aren't described there.

## Layout

- `smileid/generated/` — generator-owned code, produced from the OpenAPI specs. Do not hand-edit files here once the generator is wired up.
- `smileid/client/` — hand-written client code (configuration, request signing, transport).
- `smileid/errors/` — hand-written error types.
- `smileid/helpers/` — hand-written convenience helpers.

At this stage the repository is a scaffold only: these directories don't exist yet, and no SDK code has been written.

## Running tests

```bash
python -m pytest
```

Lint with `ruff check .` and type-check with `mypy smileid`.

## Org-wide conventions

Org-wide agent conventions for Smile ID repositories live at [smileidentity/agents](https://github.com/smileidentity/agents) (private repository, internal contributors only).
