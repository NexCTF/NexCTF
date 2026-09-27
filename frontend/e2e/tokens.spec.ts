import { submitPath, tokenApi, uniqueName } from "./support/api";
import { CAESAR_DECRYPT } from "./support/challenges";
import { expect, test } from "./support/fixtures";

test("a player creates a read-only API token, uses it, then revokes it", async ({
  page,
  signedIn,
  team: _,
}) => {
  const name = uniqueName("token");
  await page.goto("/settings");
  await expect(page.getByText("No tokens yet.")).toBeVisible();

  await page.getByRole("button", { name: "New Token" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Name").fill(name);
  await expect(dialog.getByRole("button", { name: "Save" })).toBeDisabled();
  await dialog.getByRole("button", { name: "All read", exact: true }).click();
  await dialog.getByRole("button", { name: "Save" }).click();

  await expect(dialog.getByRole("heading", { name: "Token created" })).toBeVisible();
  const token = await dialog.locator("code").innerText();
  expect(token).toMatch(/^nexctf_/);
  await dialog.getByRole("button", { name: "Done" }).click();
  await expect(page.getByText(name)).toBeVisible();

  const api = await tokenApi(token);
  const me = await api.get("info/me");
  expect(me.status(), await me.text()).toBe(200);
  expect((await me.json()).data.username).toBe(signedIn.username);
  // Read scopes only: flag submission needs write:challenge.
  const submit = await api.post(submitPath(CAESAR_DECRYPT), { data: { answer: "nexctf{nope}" } });
  expect(submit.status()).toBe(403);

  await page.getByRole("button", { name: "Revoke token" }).click();
  await expect(page.getByRole("dialog")).toContainText(`Revoke token "${name}"?`);
  await page.getByRole("dialog").getByRole("button", { name: "Delete" }).click();
  await expect(page.getByText("Token revoked")).toBeVisible();
  await expect(page.getByText(name)).toHaveCount(0);

  expect((await api.get("info/me")).status()).toBe(401);
  await api.dispose();
});

test("a token with write access can submit flags", async ({ page, team: _ }) => {
  await page.goto("/settings");
  await page.getByRole("button", { name: "New Token" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Name").fill(uniqueName("token"));
  // The radios are visually hidden; their labels are what the player clicks.
  const readWrite = dialog.getByRole("radio", { name: "Challenges and attachments: Read & write" });
  await readWrite.locator("xpath=..").click();
  await expect(readWrite).toBeChecked();
  await dialog.getByRole("button", { name: "Save" }).click();
  const token = await dialog.locator("code").innerText();

  const api = await tokenApi(token);
  const submit = await api.post(submitPath(CAESAR_DECRYPT), {
    data: { answer: CAESAR_DECRYPT.flag },
  });
  expect(submit.status(), await submit.text()).toBe(200);
  expect((await submit.json()).data.is_correct).toBe(true);
  await api.dispose();
});
