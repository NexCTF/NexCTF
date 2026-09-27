import { createHmac } from "node:crypto";
import { type APIRequestContext, expect, type Locator } from "@playwright/test";

const BASE32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";

function base32Decode(secret: string): Buffer {
  let bits = "";
  for (const char of secret.replace(/=+$/, "").toUpperCase()) {
    bits += BASE32.indexOf(char).toString(2).padStart(5, "0");
  }
  const bytes = bits.match(/.{8}/g) ?? [];
  return Buffer.from(bytes.map((byte) => Number.parseInt(byte, 2)));
}

/** The current RFC 6238 code (SHA-1, 6 digits, 30 s), as authenticator apps compute it. */
export function totpCode(secret: string, now = Date.now()): string {
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(now / 30_000)));
  const hmac = createHmac("sha1", base32Decode(secret)).update(counter).digest();
  const offset = hmac[hmac.length - 1] & 0x0f;
  const value = hmac.readUInt32BE(offset) & 0x7fffffff;
  return (value % 1_000_000).toString().padStart(6, "0");
}

/** Turn 2FA on for whoever `api` is signed in as; returns the secret. */
export async function enableTotp(api: APIRequestContext): Promise<string> {
  const setup = await api.post("/api/v1/me/totp/setup");
  expect(setup.ok(), await setup.text()).toBe(true);
  const uri: string = (await setup.json()).data.provisioning_uri;
  const secret = new URL(uri).searchParams.get("secret") as string;
  const enable = await api.post("/api/v1/me/totp/enable", { data: { code: totpCode(secret) } });
  expect(enable.status(), await enable.text()).toBe(204);
  return secret;
}

/** Type a code into the six-box OTP field inside `scope`; focus moves box to box. */
export async function typeOtp(scope: Locator, code: string): Promise<void> {
  await scope.getByRole("textbox").first().click();
  await scope.page().keyboard.type(code);
}
