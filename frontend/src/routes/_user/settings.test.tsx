import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { beforeEach, expect, it, vi } from "vitest";
import {
  ApiError,
  changePassword,
  createMyToken,
  deleteMyOAuthAccount,
  deleteMyToken,
  getMyOAuthAccounts,
  getMyTokens,
  getPublicInfo,
  totpSetup,
} from "@/lib/api";
import type { AuthContext } from "@/lib/auth";
import { paginated, publicInfo, user } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { Route } from "./settings";

const renderSettings = (auth: Partial<AuthContext> = { user: user() }) =>
  renderRoute(Route, { path: "/settings", auth });

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getPublicInfo: vi.fn(),
  getMyTokens: vi.fn(),
  getMyOAuthAccounts: vi.fn(),
  createMyToken: vi.fn(),
  deleteMyToken: vi.fn(),
  deleteMyOAuthAccount: vi.fn(),
  changePassword: vi.fn(),
  totpSetup: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));

beforeEach(() => {
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfo());
  vi.mocked(getMyTokens).mockResolvedValue(paginated([]));
  vi.mocked(getMyOAuthAccounts).mockResolvedValue([]);
});

async function fillPasswordForm(next: string, confirm: string) {
  await userEvent.type(await screen.findByLabelText("Current password"), "old");
  await userEvent.type(screen.getByLabelText("New password"), next);
  await userEvent.type(screen.getByLabelText("Confirm new password"), confirm);
  await userEvent.click(screen.getByRole("button", { name: "Change password" }));
}

it("changes the password", async () => {
  vi.mocked(changePassword).mockResolvedValue(undefined);
  renderSettings();
  await fillPasswordForm("new", "new");

  await waitFor(() => expect(changePassword).toHaveBeenCalledWith("old", "new"));
  expect(toast.success).toHaveBeenCalledWith("Password changed");
});

it("refuses a mismatched confirmation without calling the API", async () => {
  renderSettings();
  await fillPasswordForm("new", "different");

  expect(toast.error).toHaveBeenCalledWith("Passwords do not match");
  expect(changePassword).not.toHaveBeenCalled();
});

it("names the wrong-current-password case specifically", async () => {
  vi.mocked(changePassword).mockRejectedValue(new ApiError(401, "Unauthorized", null, "AUTH-401"));
  renderSettings();
  await fillPasswordForm("new", "new");

  await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Current password is incorrect"));
});

it("hides the password form for an OAuth-only account", async () => {
  renderSettings({ user: user({ has_password: false }) });

  expect(await screen.findByRole("heading", { name: "Settings" })).toBeDefined();
  expect(screen.queryByLabelText("Current password")).toBeNull();
});

it("shows the 2FA status and offers to enable it", async () => {
  renderSettings();

  expect(await screen.findByText("2FA is disabled")).toBeDefined();
  expect(screen.getByRole("button", { name: "Enable 2FA" })).toBeDefined();
  expect(screen.queryByRole("button", { name: "Disable 2FA" })).toBeNull();
});

it("offers to disable 2FA once it is on", async () => {
  renderSettings({ user: user({ totp_enabled: true }) });

  expect(await screen.findByText("2FA is enabled")).toBeDefined();
  expect(screen.getByRole("button", { name: "Disable 2FA" })).toBeDefined();
});

it("shows the QR code and the manual key when 2FA setup starts", async () => {
  vi.mocked(totpSetup).mockResolvedValue({
    provisioning_uri: "otpauth://totp/NexCTF:player?secret=JBSWY3DPEHPK3PXP&issuer=NexCTF",
  });
  renderSettings();

  await userEvent.click(await screen.findByRole("button", { name: "Enable 2FA" }));

  expect(await screen.findByText("JBSWY3DPEHPK3PXP")).toBeDefined();
  expect(screen.getByRole("button", { name: "Next" })).toBeDefined();
});

it("shows an empty state when there are no API tokens", async () => {
  renderSettings();

  expect(await screen.findByText("No tokens yet. Create one to get started.")).toBeDefined();
});

it("lists tokens and asks before revoking one", async () => {
  vi.mocked(getMyTokens).mockResolvedValue(
    paginated([{ id: "tok1", name: "CI", created_at: "2026-01-01T00:00:00Z", expires_at: null }]),
  );
  vi.mocked(deleteMyToken).mockResolvedValue(undefined);
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
  renderSettings();

  const revoke = await screen.findByRole("button", { name: "Revoke token" });
  await userEvent.click(revoke);
  expect(confirmSpy).toHaveBeenCalledWith('Revoke token "CI"?');
  expect(deleteMyToken).not.toHaveBeenCalled();

  confirmSpy.mockReturnValue(true);
  await userEvent.click(revoke);
  await waitFor(() => expect(deleteMyToken).toHaveBeenCalledWith("tok1"));
});

it("shows a freshly created token once, for copying", async () => {
  vi.mocked(createMyToken).mockResolvedValue({
    id: "tok1",
    name: "CI",
    created_at: "2026-01-01T00:00:00Z",
    expires_at: null,
    token: "nex_secret_value",
  });
  renderSettings();

  await userEvent.click(await screen.findByRole("button", { name: "New Token" }));
  await userEvent.type(await screen.findByLabelText("Name"), "CI");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));

  expect(await screen.findByText("nex_secret_value")).toBeDefined();
});

it("hides the OAuth section when the CTF has no providers", async () => {
  renderSettings();

  expect(await screen.findByRole("heading", { name: "API Tokens" })).toBeDefined();
  expect(screen.queryByRole("heading", { name: "Connected Accounts" })).toBeNull();
});

it("offers to connect an unlinked provider and to unlink a linked one", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(
    publicInfo({
      oauth_providers: [
        { slug: "github", name: "GitHub", icon_url: null },
        { slug: "gitlab", name: "GitLab", icon_url: null },
      ],
    }),
  );
  vi.mocked(getMyOAuthAccounts).mockResolvedValue([
    { id: "acc1", provider_slug: "github", provider_name: "GitHub", provider_icon_url: null },
  ]);
  vi.mocked(deleteMyOAuthAccount).mockResolvedValue(undefined);
  vi.spyOn(window, "confirm").mockReturnValue(true);
  renderSettings();

  expect(await screen.findByRole("heading", { name: "Connected Accounts" })).toBeDefined();
  expect(screen.getByRole("link", { name: "Connect" })).toBeDefined();

  await userEvent.click(screen.getByRole("button", { name: "Unlink" }));
  await waitFor(() => expect(deleteMyOAuthAccount).toHaveBeenCalledWith("acc1"));
  expect(toast.success).toHaveBeenCalledWith("GitHub unlinked");
});

it("sends an anonymous visitor to the login page", async () => {
  const { router } = renderSettings({ user: null });

  await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
  expect(getMyTokens).not.toHaveBeenCalled();
});
