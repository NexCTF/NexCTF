/** Error code the API answers when a sensitive action needs a fresh sign-in. */
export const REAUTH_REQUIRED = "AUTH-REAUTH-REQUIRED";

type ReauthPrompt = () => Promise<boolean>;

let prompt: ReauthPrompt | null = null;
let pending: Promise<boolean> | null = null;

/** Register the UI asking the user to confirm their identity; null unregisters it. */
export function setReauthPrompt(next: ReauthPrompt | null): void {
  prompt = next;
  pending = null;
}

/**
 * Ask the user to sign in again. Concurrent callers share one prompt.
 * Resolves false when dismissed or when no prompt is mounted.
 */
export function promptReauth(): Promise<boolean> {
  if (!prompt) return Promise.resolve(false);
  pending ??= prompt().finally(() => {
    pending = null;
  });
  return pending;
}
