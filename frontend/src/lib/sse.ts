/**
 * Singleton SSE connection manager.
 *
 * One EventSource is shared across the app. Components subscribe to typed
 * events via `addSSEListener` (which returns its unsubscribe function), or use
 * the `useSSEEvent` React hook. Listeners are kept here, so a replacement
 * connection picks them all up.
 */

const SSE_URL = "/api/v1/stream";
const RETRY_MIN_MS = 1_000;
const RETRY_MAX_MS = 30_000;

type Listener = (e: MessageEvent<string>) => void;

const listeners = new Map<string, Set<Listener>>();
let instance: EventSource | null = null;
let retryTimer: ReturnType<typeof setTimeout> | null = null;
let retryDelay = RETRY_MIN_MS;
let sessionChecked = false;

/** Reconnect *es* later, unless the session is gone (then send the user to sign in). */
async function recover(es: EventSource): Promise<void> {
  if (!sessionChecked) {
    // EventSource doesn't expose HTTP status — probe auth to detect 401
    const res = await fetch("/api/v1/info/me", { credentials: "include" }).catch(() => null);
    if (instance !== es) return;
    if (res?.status === 401) {
      window.location.href = "/login";
      return;
    }
    sessionChecked = true;
  }
  retryTimer = setTimeout(connect, retryDelay * (0.5 + Math.random() / 2));
  retryDelay = Math.min(retryDelay * 2, RETRY_MAX_MS);
}

function connect(): void {
  const es = new EventSource(SSE_URL, { withCredentials: true });
  for (const [eventType, set] of listeners) {
    for (const listener of set) es.addEventListener(eventType, listener);
  }
  es.onopen = () => {
    retryDelay = RETRY_MIN_MS;
    sessionChecked = false;
  };
  es.onerror = () => {
    // The browser retries a dropped stream on its own; a refused one stays closed.
    if (es.readyState === EventSource.CLOSED && instance === es) void recover(es);
  };
  retryTimer = null;
  instance = es;
}

export function addSSEListener<T = unknown>(
  eventType: string,
  handler: (data: T) => void,
): () => void {
  const listener: Listener = (e) => {
    try {
      handler(JSON.parse(e.data) as T);
    } catch {
      handler(e.data as unknown as T);
    }
  };
  if (!listeners.has(eventType)) listeners.set(eventType, new Set());
  listeners.get(eventType)?.add(listener);
  if (instance) instance.addEventListener(eventType, listener);
  else connect();

  return () => {
    listeners.get(eventType)?.delete(listener);
    instance?.removeEventListener(eventType, listener);
  };
}

/** Drop the connection; the next listener opens a fresh one as the current user. */
export function closeSSE() {
  instance?.close();
  instance = null;
  if (retryTimer) clearTimeout(retryTimer);
  retryTimer = null;
  retryDelay = RETRY_MIN_MS;
  sessionChecked = false;
}
