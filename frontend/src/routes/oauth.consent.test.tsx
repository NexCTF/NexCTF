import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError, approveOAuthConsent, getOAuthConsentInfo } from "@/lib/api";
import type { AuthContext } from "@/lib/auth";
import { user } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { Route } from "./oauth.consent";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getOAuthConsentInfo: vi.fn(),
  approveOAuthConsent: vi.fn(),
}));

const CONSENT_URL =
  "/oauth/consent?client_id=app1&redirect_uri=https%3A%2F%2Fapp.example%2Fcb&scope=openid+profile&state=xyz";

const renderConsent = (path = CONSENT_URL, auth: Partial<AuthContext> = { user: user() }) =>
  renderRoute(Route, { path, auth });

beforeEach(() => {
  vi.mocked(getOAuthConsentInfo).mockResolvedValue({
    client_id: "app1",
    client_name: "Scoreboard Bot",
    client_description: "Reads your rank",
    requested_scopes: ["openid", "profile"],
    username: "player",
  });
  vi.stubGlobal("location", { ...window.location, href: "" });
});

it("lists the requested scopes for the named client", async () => {
  renderConsent();

  expect(
    await screen.findByText("Scoreboard Bot is requesting access to your account"),
  ).toBeDefined();
  expect(screen.getByText("Reads your rank")).toBeDefined();
  expect(screen.getByText("Identify you with a unique user ID")).toBeDefined();
  expect(screen.getByText("Read your username")).toBeDefined();
  expect(screen.getByText("Signed in as player")).toBeDefined();
});

it("redirects to the client on approval", async () => {
  vi.mocked(approveOAuthConsent).mockResolvedValue({
    redirect_to: "https://app.example/cb?code=1",
  });
  renderConsent();

  await userEvent.click(await screen.findByRole("button", { name: "Allow" }));

  await waitFor(() =>
    expect(approveOAuthConsent).toHaveBeenCalledWith({
      client_id: "app1",
      redirect_uri: "https://app.example/cb",
      scope: "openid profile",
      state: "xyz",
    }),
  );
  await waitFor(() => expect(window.location.href).toBe("https://app.example/cb?code=1"));
});

it("bounces back with access_denied and the state on refusal", async () => {
  renderConsent();

  await userEvent.click(await screen.findByRole("button", { name: "Deny" }));

  expect(window.location.href).toBe("https://app.example/cb?error=access_denied&state=xyz");
  expect(approveOAuthConsent).not.toHaveBeenCalled();
});

it("keeps a query string the redirect_uri already carries on refusal", async () => {
  renderConsent(
    "/oauth/consent?client_id=app1&redirect_uri=https%3A%2F%2Fapp.example%2Fcb%3Ftenant%3Dacme&scope=openid&state=xyz",
  );

  await userEvent.click(await screen.findByRole("button", { name: "Deny" }));

  expect(window.location.href).toBe(
    "https://app.example/cb?tenant=acme&error=access_denied&state=xyz",
  );
});

it("rejects a request with no client_id", async () => {
  renderConsent("/oauth/consent");

  expect(await screen.findByText("Invalid authorization request")).toBeDefined();
});

it("explains a role that is not allowed to use the client", async () => {
  vi.mocked(getOAuthConsentInfo).mockRejectedValue(new ApiError(403, "Forbidden"));
  renderConsent();

  expect(await screen.findByText("Access denied")).toBeDefined();
});

it("sends an anonymous visitor to log in first", async () => {
  const { router } = renderConsent(CONSENT_URL, { user: null });

  await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
  expect(getOAuthConsentInfo).not.toHaveBeenCalled();
});
