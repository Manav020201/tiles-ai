# Local files connector (MCP)

A **real** connector — `kind: mcp` — not a mock. It launches the bundled
[example MCP server](../../examples/mcp_servers/files_server.py) over stdio and
exposes filesystem tools, confined to `./sample_docs`:

- `list_dir`, `read_file`, `find_files` — read-only
- `move_file` — side-effectful (moves a file; gated behind approval)

It's the proof of the project's core bet: a connector is a binding to an app's
MCP server, and it satisfies the exact same `Connector` interface as the mock —
so tiles binding it are unchanged. Four tiles bind it:
[Ask My Files](../../tiles/ask-my-files), [Summarize Folder](../../tiles/summarize-folder),
[Find Files](../../tiles/find-files), and [Tidy Folder](../../tiles/tidy-folder).

Point the `endpoint` at a real folder you care about (e.g. `~/Downloads`) and the
tiles work on it.

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
