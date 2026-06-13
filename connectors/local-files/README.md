# Local files connector (MCP)

A **real** connector — `kind: mcp` — not a mock. It launches the bundled
[example MCP server](../../examples/mcp_servers/files_server.py) over stdio and
exposes its read-only filesystem tools (`list_dir`, `read_file`), confined to
`./sample_docs`.

It's the proof of the project's core bet: a connector is a binding to an app's
MCP server, and it satisfies the exact same `Connector` interface as the mock —
so tiles binding it are unchanged.

## Point it elsewhere

Edit `endpoint` in `manifest.yaml` to launch any MCP server:

```yaml
endpoint: "python3 examples/mcp_servers/files_server.py /path/to/notes"
# or any other MCP stdio server, e.g.:
# endpoint: "npx -y @modelcontextprotocol/server-filesystem /path"
```

Keep the `tools` list in sync with what the server exposes — it's the surface
tiles are allow-listed against and the authority the permission gate trusts. Use
`MCPConnector.live_tools()` to introspect a running server while authoring.
