# connectors/

Each subfolder is one **connector** — the durable connection to one application.

```
connectors/<connector_id>/
  manifest.yaml   # ConnectorManifest: id, app, kind, endpoint?, auth, tools
  adapter.py      # implements tiles_ai.contracts.Connector
```

The registry (phase 2) discovers and validates every folder here. v0 ships a
`mock` connector; a real MCP-backed connector implements the same `Connector`
interface and drops in unchanged. See [`../SPEC.md`](../SPEC.md).
