// Wire types mirroring tiles_ai/api/schemas.py. Keep in sync with the backend.

export interface Brain {
  source: "default" | "pinned";
  label: string;
  provider: string;
  model: string;
  endpoint?: string | null;
}

export interface Tile {
  id: string;
  name: string;
  description: string;
  icon: string;
  connector: string | null;
  permission_tier: "read_only" | "draft" | "autonomous";
  state: "defined" | "available" | "active" | "paused" | "stopped" | "composed";
  allowed_tools: string[];
  uses_default_brain: boolean;
  brain: Brain | null;
  needs_brain: boolean;
  wants_input: boolean;
  input_hint: string | null;
  connector_ready: boolean;
  missing_env: string[];
  schedule: string | null;
}

export interface TileDetail extends Tile {
  instructions: string;
  provides: { name: string; description?: string }[];
  consumes: { name: string; description?: string }[];
}

export interface RunResponse {
  tile_id: string;
  result: unknown;
  executed: { tool: string; ok: boolean; output: unknown }[];
  queued: { approval_id: string; tool: string; summary: string; args: Record<string, unknown> }[];
  rejected: { tool: string }[];
}

export interface Approval {
  id: string;
  tile_id: string;
  tool: string;
  args: Record<string, unknown>;
  summary: string;
  side_effect: boolean;
  status: "pending" | "executed" | "rejected";
  output: unknown;
}

export interface Provider {
  id: string;
  kind: "hosted" | "local";
  provider?: string | null;
  endpoint?: string | null;
  model: string;
  is_default: boolean;
}

export interface TilesEvent {
  type: string;
  tile_id: string | null;
  data: Record<string, unknown>;
  ts: number | null;
}

export interface ConnectorTool {
  name: string;
  description: string;
  side_effect: boolean;
}

export interface Connector {
  id: string;
  app: string;
  kind: string;
  endpoint?: string | null;
  env?: string[];
  tools: ConnectorTool[];
}

export interface NewTile {
  name: string;
  icon?: string;
  description?: string;
  instructions?: string;
  permission_tier?: string;
  connector?: string | null;
  allowed_tools?: string[];
  wants_input?: boolean;
  input_hint?: string | null;
  schedule?: string | null;
}

export interface NewConnector {
  app: string;
  kind?: string;
  endpoint?: string | null;
  env?: string[];
  tools?: ConnectorTool[];
}

export interface LoadError {
  kind: string;
  source: string;
  errors: string[];
}

export interface FlowStep {
  tile_id: string;
  result: unknown;
  queued: number;
  executed: number;
  rejected: number;
}

export interface FlowRun {
  steps: FlowStep[];
}
