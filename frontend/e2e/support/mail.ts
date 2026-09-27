import { expect, request } from "@playwright/test";

/** Mailpit, which captures every email the dev backend sends. */
const MAILPIT_URL = process.env.E2E_MAILPIT_URL ?? "http://localhost:8025";

interface MailpitSummary {
  ID: string;
}

/** Wait for the newest email sent to `to` and return its plain-text body. */
export async function latestEmailTo(to: string): Promise<string> {
  const mailpit = await request.newContext({ baseURL: MAILPIT_URL });
  try {
    let id: string | undefined;
    await expect
      .poll(
        async () => {
          const res = await mailpit.get("/api/v1/search", { params: { query: `to:"${to}"` } });
          const { messages } = (await res.json()) as { messages: MailpitSummary[] };
          id = messages[0]?.ID;
          return id;
        },
        { message: `no email reached ${to}`, timeout: 15_000 },
      )
      .toBeTruthy();
    const res = await mailpit.get(`/api/v1/message/${id}`);
    return (await res.json()).Text as string;
  } finally {
    await mailpit.dispose();
  }
}

/** The path and query of the first link in `body` pointing at `pathname`. */
export function linkPath(body: string, pathname: string): string {
  const match = new RegExp(`https?://[^\\s/]+(${pathname}\\?token=[\\w.~-]+)`).exec(body);
  expect(match, `no ${pathname} link in:\n${body}`).not.toBeNull();
  return (match as RegExpExecArray)[1];
}
