import { expect } from "@playwright/test";
import { adminApi } from "./api";

/** Every test signs in and submits from the same address, so the per-IP limits must go. */
const OVERRIDES: Record<string, string> = {
  "rate_limit.login.enabled": "false",
  "rate_limit.submit.enabled": "false",
};

interface ConfigItem {
  key: string;
  value: unknown;
}

async function putConfig(items: Record<string, string>): Promise<void> {
  const admin = await adminApi();
  try {
    const res = await admin.put("admin/config", { data: { items } });
    expect(res.ok(), await res.text()).toBe(true);
  } finally {
    await admin.dispose();
  }
}

/** Lift the rate limits for the run; the returned teardown restores them. */
export default async function globalSetup(): Promise<() => Promise<void>> {
  const admin = await adminApi();
  const res = await admin.get("admin/config");
  expect(res.ok(), `admin API unreachable: ${await res.text()}`).toBe(true);
  const items: ConfigItem[] = (await res.json()).data;
  await admin.dispose();

  const previous = Object.fromEntries(
    items.filter((item) => item.key in OVERRIDES).map((item) => [item.key, String(item.value)]),
  );
  await putConfig(OVERRIDES);
  return () => putConfig(previous);
}
