/**
 * Singleton SSE connection manager.
 *
 * One EventSource is shared across the app. Components subscribe to typed
 * events via `addSSEListener` / `removeSSEListener`, or use the
 * `useSSEEvent` React hook.
 */

const SSE_URL = "/api/v1/stream";

let instance: EventSource | null = null;

let authProbing = false;

function getOrCreate(): EventSource {
  if (!instance || instance.readyState === EventSource.CLOSED) {
    const es = new EventSource(SSE_URL, { withCredentials: true });

    es.onerror = () => {
      if (authProbing) return;
      authProbing = true;
      // EventSource doesn't expose HTTP status — probe auth to detect 401
      fetch("/api/v1/info/me", { credentials: "include" })
        .then((res) => {
          if (res.status === 401) window.location.href = "/login";
        })
        .catch(() => {})
        .finally(() => {
          authProbing = false;
        });
    };

    instance = es;
  }
  return instance;
}

export function addSSEListener<T = unknown>(
  eventType: string,
  handler: (data: T) => void,
): () => void {
  const es = getOrCreate();

  const listener = (e: MessageEvent<string>) => {
    try {
      handler(JSON.parse(e.data) as T);
    } catch {
      handler(e.data as unknown as T);
    }
  };

  es.addEventListener(eventType, listener);
  return () => es.removeEventListener(eventType, listener);
}

export function closeSSE() {
  instance?.close();
  instance = null;
}
