import { useState } from "react";
import { api, ApiError } from "../api";

type Path = "choose" | "cloud" | "local";

// First-launch "Connect a brain" flow. Cloud (API key) or local (endpoint),
// each ending in a Test -> green check. The provider becomes the default brain
// and the beginner is done.
export function Onboarding({ onDone }: { onDone: () => void }) {
  const [path, setPath] = useState<Path>("choose");

  if (path === "choose") {
    return (
      <div className="onboarding">
        <h1>Connect a brain</h1>
        <p className="onboarding-sub">
          Every tile uses one default brain. Pick how you want to power them.
        </p>
        <div className="choice-grid">
          <button className="choice" onClick={() => setPath("cloud")}>
            <div className="choice-icon">☁️</div>
            <div className="choice-title">Use a cloud AI</div>
            <div className="choice-desc">Powerful. Needs an API key.</div>
          </button>
          <button className="choice" onClick={() => setPath("local")}>
            <div className="choice-icon">💻</div>
            <div className="choice-title">Use an AI on my computer</div>
            <div className="choice-desc">Free & private. Needs a local endpoint.</div>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="onboarding">
      <button className="link-back" onClick={() => setPath("choose")}>
        ← back
      </button>
      {path === "cloud" ? <CloudForm onDone={onDone} /> : <LocalForm onDone={onDone} />}
    </div>
  );
}

function CloudForm({ onDone }: { onDone: () => void }) {
  const [provider, setProvider] = useState("anthropic");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("claude-opus-4-8");
  return (
    <BrainForm
      title="Cloud AI"
      onDone={onDone}
      build={() => ({
        id: `cloud-${provider}`,
        kind: "hosted",
        provider,
        api_key: apiKey,
        model,
      })}
      canTest={apiKey.length > 0 && model.length > 0}
    >
      <label className="field">
        <span>Provider</span>
        <select value={provider} onChange={(e) => setProvider(e.target.value)}>
          <option value="anthropic">Anthropic</option>
          <option value="openai">OpenAI</option>
        </select>
      </label>
      <label className="field">
        <span>API key</span>
        <input
          type="password"
          value={apiKey}
          placeholder="sk-…"
          onChange={(e) => setApiKey(e.target.value)}
        />
      </label>
      <label className="field">
        <span>Model</span>
        <input value={model} onChange={(e) => setModel(e.target.value)} />
      </label>
    </BrainForm>
  );
}

function LocalForm({ onDone }: { onDone: () => void }) {
  const [endpoint, setEndpoint] = useState("http://localhost:11434");
  const [model, setModel] = useState("llama3");
  return (
    <BrainForm
      title="Local AI"
      onDone={onDone}
      build={() => ({ id: "local", kind: "local", endpoint, model })}
      canTest={endpoint.length > 0 && model.length > 0}
    >
      <label className="field">
        <span>Endpoint</span>
        <input value={endpoint} onChange={(e) => setEndpoint(e.target.value)} />
      </label>
      <label className="field">
        <span>Model</span>
        <input value={model} onChange={(e) => setModel(e.target.value)} />
      </label>
    </BrainForm>
  );
}

function BrainForm({
  title,
  children,
  build,
  canTest,
  onDone,
}: {
  title: string;
  children: React.ReactNode;
  build: () => Record<string, unknown>;
  canTest: boolean;
  onDone: () => void;
}) {
  const [status, setStatus] = useState<"idle" | "saving" | "ok" | "error">("idle");
  const [detail, setDetail] = useState("");

  async function saveAndTest() {
    setStatus("saving");
    setDetail("");
    try {
      const provider = build();
      await api.addProvider(provider, true); // first provider -> default
      const result = await api.testProvider(provider.id as string);
      if (result.ok) {
        setStatus("ok");
        setDetail(result.detail);
      } else {
        setStatus("error");
        setDetail(result.detail);
      }
    } catch (e) {
      setStatus("error");
      setDetail(e instanceof ApiError ? e.message : String(e));
    }
  }

  return (
    <div className="brain-form">
      <h1>{title}</h1>
      {children}
      <div className="form-actions">
        <button className="btn btn-primary" onClick={saveAndTest} disabled={!canTest || status === "saving"}>
          {status === "saving" ? "Testing…" : "Save & test"}
        </button>
        {status === "ok" && <span className="test-ok">✓ working</span>}
        {status === "error" && <span className="test-error">✕ {detail}</span>}
      </div>
      {status === "ok" && (
        <button className="btn btn-done" onClick={onDone}>
          Go to my board →
        </button>
      )}
    </div>
  );
}
