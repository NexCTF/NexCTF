import { useState, useEffect, useCallback } from "react";
import type { ChallengePanelProps } from "./sdk";

interface OrchestratorInstance {
  id: string;
  challenge_id: string;
  status: string;
  start_date: string;
  stop_date: string;
  urls: string[];
}

async function apiFetch(
  path: string,
  method = "GET",
  signal?: AbortSignal,
): Promise<{ data: OrchestratorInstance | null }> {
  const r = await fetch(path, { method, credentials: "include", signal });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

function formatCountdown(ms: number): string {
  if (ms <= 0) return "00m 00s";
  const total = Math.floor(ms / 1000);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}h ${mm}m ${ss}s` : `${mm}m ${ss}s`;
}

function useCountdown(stopDate: string | undefined): number {
  const [remaining, setRemaining] = useState(0);
  useEffect(() => {
    if (!stopDate) return;
    const tick = () => Math.max(0, new Date(stopDate).getTime() - Date.now());
    setRemaining(tick());
    const id = setInterval(() => setRemaining(tick()), 1000);
    return () => clearInterval(id);
  }, [stopDate]);
  return remaining;
}

export default function ChallengePanel({ challenge }: ChallengePanelProps) {
  const [instance, setInstance] = useState<OrchestratorInstance | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Initial fetch — AbortController ensures only one request completes
  // even when the effect runs twice (StrictMode / Suspense remount).
  useEffect(() => {
    const controller = new AbortController();
    setBusy(true);
    apiFetch(
      `/api/v1/orchestrator/status?challenge_id=${challenge.id}`,
      "GET",
      controller.signal,
    )
      .then(({ data }) => {
        setInstance(data);
        setError(null);
      })
      .catch((e: Error) => {
        if (e.name !== "AbortError") setError(e.message);
      })
      .finally(() => setBusy(false));
    return () => controller.abort();
  }, [challenge.id]);

  const running = instance?.status === "running";

  // Silent background poll — no busy spinner every 10 s.
  const silentRefetch = useCallback(async () => {
    try {
      const { data } = await apiFetch(
        `/api/v1/orchestrator/status?challenge_id=${challenge.id}`,
      );
      setInstance(data);
    } catch {
      // swallow polling errors silently
    }
  }, [challenge.id]);

  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => void silentRefetch(), 10_000);
    return () => clearInterval(id);
  }, [running, silentRefetch]);

  const remaining = useCountdown(running ? instance?.stop_date : undefined);

  const act = useCallback(
    async (action: "start" | "stop" | "renew") => {
      if (busy) return;
      setBusy(true);
      setError(null);
      try {
        const { data } = await apiFetch(
          `/api/v1/orchestrator/${action}?challenge_id=${challenge.id}`,
          "POST",
        );
        setInstance(data);
      } catch (e) {
        setError(String(e));
      } finally {
        setBusy(false);
      }
    },
    [challenge.id, busy],
  );

  const expired = running && remaining === 0;
  const countdownColor = remaining < 5 * 60 * 1000 ? "#dc2626" : "#334155";

  return (
    <div style={panel}>
      <div style={row}>
        <span style={label}>Instance</span>
        <span
          style={{
            ...badge,
            background: running ? "#dcfce7" : "#f1f5f9",
            color: running ? "#166534" : "#475569",
          }}
        >
          {busy ? "…" : instance ? instance.status : "not started"}
        </span>
      </div>

      {running && (
        <>
          <div style={row}>
            <span style={label}>Expires</span>
            <span
              style={{
                color: expired ? "#dc2626" : countdownColor,
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {expired ? "expired" : formatCountdown(remaining)}
            </span>
          </div>
          {instance!.urls.map((url) => (
            <div key={url} style={row}>
              <span style={label}>URL</span>
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: "#2563eb" }}
              >
                {url}
              </a>
            </div>
          ))}
        </>
      )}

      {error && (
        <div style={{ color: "#dc2626", fontSize: "12px", marginTop: "6px" }}>
          {error}
        </div>
      )}

      <div style={{ display: "flex", gap: "8px", marginTop: "10px" }}>
        {!running && (
          <button style={btn} disabled={busy} onClick={() => act("start")}>
            Start
          </button>
        )}
        {running && (
          <>
            <button style={btn} disabled={busy} onClick={() => act("renew")}>
              Renew
            </button>
            <button
              style={{ ...btn, background: "#fee2e2", color: "#991b1b" }}
              disabled={busy}
              onClick={() => act("stop")}
            >
              Stop
            </button>
          </>
        )}
      </div>
    </div>
  );
}

const panel: React.CSSProperties = {
  border: "1px solid #e2e8f0",
  borderRadius: "8px",
  padding: "14px 16px",
  marginBottom: "8px",
  fontSize: "14px",
  color: "#334155",
};

const row: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "10px",
  marginBottom: "4px",
};

const label: React.CSSProperties = {
  minWidth: "60px",
  color: "#94a3b8",
  fontSize: "12px",
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
};

const badge: React.CSSProperties = {
  padding: "2px 8px",
  borderRadius: "9999px",
  fontSize: "12px",
  fontWeight: 600,
};

const btn: React.CSSProperties = {
  padding: "6px 14px",
  borderRadius: "6px",
  border: "none",
  background: "#f1f5f9",
  color: "#334155",
  cursor: "pointer",
  fontSize: "13px",
  fontWeight: 500,
};
