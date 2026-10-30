let offsetMs = 0;

/** Align with *serverTime*, read from a response received between *sentAt* and *receivedAt*. */
export function syncServerClock(serverTime: string, sentAt: number, receivedAt: number): void {
  const server = Date.parse(serverTime);
  if (Number.isNaN(server)) return;
  offsetMs = server - (sentAt + receivedAt) / 2;
}

/** Milliseconds since the epoch on the server's clock. */
export function serverNow(): number {
  return Date.now() + offsetMs;
}
