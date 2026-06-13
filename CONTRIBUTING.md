# Contributing to Tiles AI

Thanks for helping build Tiles AI. This is a young, opinionated project, so a
little shared context goes a long way.

## Philosophy (please read once)

Three ideas drive every decision here. PRs that pull against them will get push-back.

1. **The contract is the spine.** [`SPEC.md`](SPEC.md) and
   [`src/tiles_ai/contracts/`](src/tiles_ai/contracts/) define what a tile, a
   connector, and a brain are. The board, runtime, API, and docs are all
   downstream. Change the contract carefully and update `SPEC.md` in the same PR.
2. **Permissions are first-class.** Any real-world side effect defaults to
   human-in-the-loop. The permission gate is the *only* path through which a
   side effect can execute — never add a way for a handler to bypass it.
3. **Inspectability over cleverness.** A newcomer should be able to read one
   reference tile end to end and copy it. Prefer obvious code; match the comment
   density and idiom of the file you're editing.

## Dev setup

Backend (Python ≥ 3.11):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Frontend (Node ≥ 18):

```bash
cd frontend
npm install
npm run build      # type-check + build
npm run dev        # board against a running backend
```

Run the whole thing with a zero-setup offline brain:

```bash
TILES_ECHO=1 python -m tiles_ai.api    # API on :8000
cd frontend && npm run dev             # board on :5173
```

## Repository layout

```
src/tiles_ai/
  contracts/    # THE SPINE — schemas, interfaces, lifecycle, permissions, brain
  registry/     # discover + validate + load connector/tile folders
  connectors/   # connector layer (mock + a real MCP-backed connector)
  model/        # brain store + model adapter (Anthropic/OpenAI/Ollama/echo)
  runtime/      # activation, permission gate + approval queue, tool/model handles
  events/       # in-process event bus
  api/          # FastAPI control plane + SSE
connectors/     # authored connector folders (discovered at runtime)
tiles/          # authored tile folders (discovered at runtime)
frontend/       # React board
tests/          # contract + integration tests
```

## Adding a tile or connector

See [`docs/AUTHORING.md`](docs/AUTHORING.md). The short version: copy a reference
folder, edit the manifest, implement one interface, add a test that proves it
loads and runs.

## Conventions

- **Async everywhere** in the connector/tile/runtime interfaces.
- **Pydantic v2** for anything that crosses a boundary (manifests, API, config).
- **Validation lives on the model**; cross-manifest checks live in
  `contracts/validation.py`. Keep the registry and gate thin callers.
- **No secrets in manifests.** Keys live only in the local brain store
  (gitignored). `ModelRef` is secret-free by construction.
- **Type-check the frontend** (`npm run build`) — `strict`, `noUnusedLocals`,
  and `noUnusedParameters` are on.

## Tests

- All contract rules and behaviors are tested; add tests with your change.
- Async tests use `asyncio.run` — no extra plugin.
- API/integration tests run fully offline via the echo client (no network, no
  keys). Don't introduce tests that require live model calls.
- Run `pytest` (backend) and `npm run build` (frontend) before opening a PR.

## Commits & PRs

- Keep commits small and scoped. Explain trade-offs in the body when a choice
  isn't obvious.
- Touching `contracts/`? Update `SPEC.md` in the same PR and call out the change.
- Out-of-scope-for-v0 features (multi-tile orchestration, scheduled triggers,
  real OAuth, live MCP servers, multi-user/hosting) — leave the seam, don't build
  it. If you think a seam is wrong, open an issue first.

## License

By contributing, you agree your contributions are licensed under the
[MIT License](LICENSE).
