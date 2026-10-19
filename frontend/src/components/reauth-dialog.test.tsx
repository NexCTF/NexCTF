import { act, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { ApiError, getMyOAuthAccounts, reauth, type User } from "@/lib/api";
import { type AuthContext, AuthCtx } from "@/lib/auth";
import { promptReauth } from "@/lib/reauth";
import { user } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";
import { ReauthDialog } from "./reauth-dialog";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  reauth: vi.fn(),
  getMyOAuthAccounts: vi.fn(),
}));

afterEach(() => {
  vi.mocked(reauth).mockReset();
  vi.mocked(getMyOAuthAccounts).mockReset();
});

function renderDialog(me: User) {
  vi.mocked(getMyOAuthAccounts).mockResolvedValue([]);
  const auth: AuthContext = { user: me, isLoading: false, login: vi.fn(), logout: vi.fn() };
  renderWithQuery(
    <AuthCtx.Provider value={auth}>
      <ReauthDialog />
    </AuthCtx.Provider>,
  );
}

async function openPrompt(): Promise<{ result: Promise<boolean>; dialog: HTMLElement }> {
  let result: Promise<boolean> = Promise.resolve(false);
  act(() => {
    result = promptReauth();
  });
  return { result, dialog: await screen.findByRole("dialog") };
}

it("confirms with the password and resolves the prompt", async () => {
  renderDialog(user());
  vi.mocked(reauth).mockResolvedValue(undefined);
  const { result, dialog } = await openPrompt();

  await userEvent.type(within(dialog).getByLabelText("Password"), "secretpass");
  await userEvent.click(within(dialog).getByRole("button", { name: "Confirm" }));

  expect(await result).toBe(true);
  expect(reauth).toHaveBeenCalledWith("secretpass", null);
  expect(screen.queryByRole("dialog")).toBeNull();
});

it("keeps the dialog open on a wrong password", async () => {
  renderDialog(user());
  vi.mocked(reauth).mockRejectedValue(
    new ApiError(401, "Invalid credentials", "The username or password is incorrect."),
  );
  const { dialog } = await openPrompt();

  await userEvent.type(within(dialog).getByLabelText("Password"), "nope");
  await userEvent.click(within(dialog).getByRole("button", { name: "Confirm" }));

  expect(await within(dialog).findByText("The username or password is incorrect.")).toBeTruthy();
  expect(screen.getByRole("dialog")).toBeTruthy();
});

it("resolves false when cancelled", async () => {
  renderDialog(user());
  const { result, dialog } = await openPrompt();

  await userEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));

  expect(await result).toBe(false);
  expect(reauth).not.toHaveBeenCalled();
});

it("asks for the code when two-factor is on", async () => {
  renderDialog(user({ totp_enabled: true }));
  const { dialog } = await openPrompt();

  expect(within(dialog).getByText("Authentication code")).toBeTruthy();
  expect(within(dialog).getByRole("button", { name: "Confirm" }).hasAttribute("disabled")).toBe(
    true,
  );
});

it("offers the linked providers to an account without a password", async () => {
  renderDialog(user({ has_password: false }));
  vi.mocked(getMyOAuthAccounts).mockResolvedValue([
    { id: "a1", provider_slug: "gh", provider_name: "GitHub", provider_icon_url: null },
  ]);
  const { dialog } = await openPrompt();

  const link = await within(dialog).findByRole("link", { name: "GitHub" });
  expect(link.getAttribute("href")).toContain("/auth/providers/gh/authorize");
  expect(within(dialog).queryByLabelText("Password")).toBeNull();
  expect(within(dialog).queryByRole("button", { name: "Confirm" })).toBeNull();
});
