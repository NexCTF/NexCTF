import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { beforeEach, expect, it, vi } from "vitest";
import {
  ApiError,
  changePassword,
  createMyToken,
  deleteAllSessions,
  deleteMyOAuthAccount,
  deleteMySession,
  deleteMyToken,
  getMyOAuthAccounts,
  getMyProfile,
  getMySessions,
  getMyTokens,
  getPublicInfo,
  totpSetup,
  updateMyProfile,
} from "@/lib/api";
import type { AuthContext } from "@/lib/auth";
import { paginated, publicInfo, publicInfoWith, user, userSession } from "@/test/fixtures";
import { clickAndCancel, clickAndConfirm, renderRoute } from "@/test/render";
import { Route } from "./settings";

const renderSettings = (auth: Partial<AuthContext> = { user: user() }) =>
  renderRoute(Route, { path: "/settings", auth });

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getPublicInfo: vi.fn(),
  getMyTokens: vi.fn(),
  getMyOAuthAccounts: vi.fn(),
  getMySessions: vi.fn(),
  createMyToken: vi.fn(),
  deleteMyToken: vi.fn(),
  deleteMySession: vi.fn(),
  deleteAllSessions: vi.fn(),
  deleteMyOAuthAccount: vi.fn(),
  changePassword: vi.fn(),
  totpSetup: vi.fn(),
  getMyProfile: vi.fn(),
  updateMyProfile: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));

beforeEach(() => {
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfo());
  vi.mocked(getMyTokens).mockResolvedValue(paginated([]));
  vi.mocked(getMyOAuthAccounts).mockResolvedValue([]);
  vi.mocked(getMySessions).mockResolvedValue([]);
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
  renderSettings();

  const revoke = await screen.findByRole("button", { name: "Revoke token" });
  await clickAndCancel(revoke);
  expect(deleteMyToken).not.toHaveBeenCalled();

  await clickAndConfirm(revoke, "Delete");
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
  renderSettings();

  expect(await screen.findByRole("heading", { name: "Connected Accounts" })).toBeDefined();
  expect(screen.getByRole("link", { name: "Connect" })).toBeDefined();

  await clickAndConfirm(screen.getByRole("button", { name: "Unlink" }), "Unlink");
  await waitFor(() => expect(deleteMyOAuthAccount).toHaveBeenCalledWith("acc1"));
  expect(toast.success).toHaveBeenCalledWith("GitHub unlinked");
});

it("sends an anonymous visitor to the login page", async () => {
  const { router } = renderSettings({ user: null });

  await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
  expect(getMyTokens).not.toHaveBeenCalled();
});

it("lists sessions and marks the current device", async () => {
  vi.mocked(getMySessions).mockResolvedValue([
    userSession({ id: "s1", current: true }),
    userSession({ id: "s2", ip: "198.51.100.9" }),
  ]);
  renderSettings();

  expect(await screen.findByText("This device")).toBeDefined();
  expect(screen.getAllByText("Chrome on Windows")).toHaveLength(2);
  // `ip` is the address the session was opened from, so the label stays
  // past-tense; the live address is shown separately when it differs.
  expect(screen.getByText(/Signed in from 198\.51\.100\.9/)).toBeDefined();
});

it("flags a session now used from a different IP", async () => {
  vi.mocked(getMySessions).mockResolvedValue([
    userSession({ id: "s1", ip: "203.0.113.7", last_ip: "198.51.100.9" }),
    userSession({ id: "s2", ip: "203.0.113.7", last_ip: "203.0.113.7" }),
  ]);
  renderSettings();

  expect(await screen.findByText(/now used from 198\.51\.100\.9/)).toBeDefined();
  expect(screen.queryByText(/now used from 203\.0\.113\.7/)).toBeNull();
});

it("offers no revoke button for the current device", async () => {
  vi.mocked(getMySessions).mockResolvedValue([userSession({ id: "s1", current: true })]);
  renderSettings();

  await screen.findByText("This device");
  expect(screen.queryByRole("button", { name: "Sign out this device" })).toBeNull();
});

it("revokes a single session", async () => {
  vi.mocked(getMySessions).mockResolvedValue([
    userSession({ id: "s1", current: true }),
    userSession({ id: "s2" }),
  ]);
  vi.mocked(deleteMySession).mockResolvedValue(undefined);
  renderSettings();

  await clickAndConfirm(
    await screen.findByRole("button", { name: "Sign out this device" }),
    "Sign out this device",
  );

  await waitFor(() => expect(deleteMySession).toHaveBeenCalledWith("s2"));
  expect(toast.success).toHaveBeenCalledWith("Session signed out");
});

it("signs out everywhere and drops this session too", async () => {
  const logout = vi.fn().mockResolvedValue(undefined);
  vi.mocked(getMySessions).mockResolvedValue([
    userSession({ id: "s1", current: true }),
    userSession({ id: "s2" }),
  ]);
  vi.mocked(deleteAllSessions).mockResolvedValue(undefined);
  renderSettings({ user: user(), logout });

  await clickAndConfirm(
    await screen.findByRole("button", { name: /Sign out everywhere/ }),
    "Sign out everywhere",
  );

  await waitFor(() => expect(deleteAllSessions).toHaveBeenCalled());
  expect(toast.success).toHaveBeenCalledWith("Signed out on every device");
  await waitFor(() => expect(logout).toHaveBeenCalled());
});

it("warns that signing out everywhere includes this device", async () => {
  vi.mocked(getMySessions).mockResolvedValue([userSession({ id: "s1", current: true })]);
  renderSettings();

  await userEvent.click(await screen.findByRole("button", { name: /Sign out everywhere/ }));

  expect(
    await screen.findByText("Sign out on every device? You will be signed out here too."),
  ).toBeDefined();
  expect(deleteAllSessions).not.toHaveBeenCalled();
});

it("keeps the session out of the list when revocation fails", async () => {
  vi.mocked(getMySessions).mockResolvedValue([
    userSession({ id: "s1", current: true }),
    userSession({ id: "s2" }),
  ]);
  vi.mocked(deleteMySession).mockRejectedValue(new ApiError(500, "boom", null, null));
  renderSettings();

  await clickAndConfirm(
    await screen.findByRole("button", { name: "Sign out this device" }),
    "Sign out this device",
  );

  await waitFor(() => expect(toast.error).toHaveBeenCalledWith("boom"));
});

const myProfile = {
  links: [],
  custom_fields: [
    {
      definition_id: "d1",
      label: "Discord",
      field_type: "string" as const,
      is_required: false,
      value: null,
    },
  ],
};

it("saves the profile when customization is on", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfoWith({ allow_user_customization: true }));
  vi.mocked(getMyProfile).mockResolvedValue(myProfile);
  vi.mocked(updateMyProfile).mockResolvedValue(myProfile);
  renderSettings();

  await userEvent.type(await screen.findByLabelText("Discord"), "player#1");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));

  await waitFor(() =>
    expect(updateMyProfile).toHaveBeenCalledWith({
      links: [],
      custom_fields: { d1: "player#1" },
    }),
  );
});

it("hides the profile form when customization is off", async () => {
  vi.mocked(getMyProfile).mockResolvedValue(myProfile);
  renderSettings();

  await screen.findByText("API Tokens");
  expect(screen.queryByText("Profile")).toBeNull();
});
