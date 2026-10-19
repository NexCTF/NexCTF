import { execFile } from "node:child_process";
import path from "node:path";
import { promisify } from "node:util";
import type { BrowserContext } from "@playwright/test";

const BACKEND = path.resolve(import.meta.dirname, "../../../backend");
const COOKIE = "NexCTF";
/** The development key from `.env.dev`, which `task` exports to the suite. */
const SECRET_KEY = process.env.SECRET_KEY ?? "changethis-changethis-changethis-changethis";

const RESIGN = `
import sys, time
from unittest.mock import patch
from fastapi_multiauth import APIKeyCookieAuth
from itsdangerous import TimestampSigner

value, secret, age = sys.argv[1], sys.argv[2], int(sys.argv[3])
cookie = APIKeyCookieAuth(
    name="${COOKIE}",
    validator=lambda credential, session_id: None,
    secret_key=secret,
    session_id=True,
)
plain = cookie._verify(value)
with patch.object(TimestampSigner, "get_timestamp", lambda _: int(time.time()) - age):
    print(cookie._sign(plain))
`;

/** Re-sign the context's session cookie as if it had been minted `seconds` ago. */
export async function ageSession(context: BrowserContext, seconds: number): Promise<void> {
  const cookie = (await context.cookies()).find((c) => c.name === COOKIE);
  if (!cookie) throw new Error("no session cookie to age");
  const { stdout } = await promisify(execFile)(
    "uv",
    ["run", "--no-sync", "python", "-I", "-c", RESIGN, cookie.value, SECRET_KEY, `${seconds}`],
    { cwd: BACKEND, encoding: "utf8" },
  );
  await context.addCookies([{ ...cookie, value: stdout.trim() }]);
}
