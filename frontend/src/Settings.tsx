import { useEffect, useState } from "react";

import { type AgentRuntime, type AppSettings, getSettings, putSettings } from "./api";

const RUNTIMES: Record<AgentRuntime, { name: string; detail: string }> = {
  gateway: { name: "API key", detail: "Our loop through the gateway. Per-token billing. Works in the Docker workers." },
  agent_sdk: {
    name: "Claude Code login",
    detail: "The Claude Agent SDK on this machine's Claude Code login (subscription). Only workers run on the host with AGENT_RUNTIMES=gateway,agent_sdk use it; Docker workers fall back to the API key.",
  },
};

/** Applies to the next agent any worker starts; nothing restarts. */
export function Settings() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSettings().then(setSettings, (e: Error) => setError(e.message));
  }, []);

  const choose = async (agent_runtime: AgentRuntime) => {
    setError(null);
    try {
      setSettings(await putSettings({ agent_runtime }));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  if (settings === null && error === null) return <p className="note">Loading settings…</p>;
  return (
    <>
      <h2 className="section-label">Agent runtime</h2>
      <fieldset className="settings__group">
        {(Object.keys(RUNTIMES) as AgentRuntime[]).map((runtime) => (
          <label key={runtime} className="settings__option">
            <input
              type="radio"
              name="agent_runtime"
              value={runtime}
              checked={settings?.agent_runtime === runtime}
              onChange={() => choose(runtime)}
            />
            <span>
              <strong>{RUNTIMES[runtime].name}</strong>
              <br />
              <span className="note">{RUNTIMES[runtime].detail}</span>
            </span>
          </label>
        ))}
      </fieldset>
      {error && (
        <p role="alert" className="note note--error">
          Could not save settings: {error}
        </p>
      )}
    </>
  );
}
