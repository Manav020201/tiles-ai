# Ask My Files

A **read_only** tile over the **real, MCP-backed** [local-files
connector](../../connectors/local-files). It lists `./sample_docs`, reads the
files, and answers your question grounded in them — citing the source file. It
never writes.

## What it demonstrates

- **A tile over a real connector.** The handler is identical to one over a mock:
  reads go through `ctx.tools`; the connector happens to be a live MCP server.
- **The connector seam works.** Point `connectors/local-files` at a different
  directory (or a different MCP server entirely) and this tile is unchanged.

## Try it

Start the API from the repo root (the connector launches the example server
relative to it), connect a brain, activate **Ask My Files**, and ask something
like *"When is the launch and who owns it?"*
