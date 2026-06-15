import type { Tile } from "../types";

// A ready-to-tweak Tile for tests.
export function makeTile(over: Partial<Tile> = {}): Tile {
  return {
    id: "ask",
    name: "Ask",
    description: "Ask anything",
    icon: "💬",
    connector: null,
    permission_tier: "read_only",
    state: "available",
    allowed_tools: [],
    uses_default_brain: true,
    brain: {
      source: "default",
      label: "default",
      provider: "anthropic",
      model: "claude-opus-4-8",
    },
    needs_brain: false,
    wants_input: true,
    input_hint: "Ask…",
    connector_ready: true,
    missing_env: [],
    schedule: null,
    ...over,
  };
}
