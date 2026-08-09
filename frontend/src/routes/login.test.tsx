import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError, getPublicInfo } from "@/lib/api";
import { publicInfo, publicInfoWith, user } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { Route } from "./login";
import { Route as ConsentRoute } from "./oauth.consent";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getPublicInfo: vi.fn(),
  logout: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfo());
});

async function fillAndSubmit() {
  await userEvent.type(await screen.findByLabelText("Username"), "alice");
  await userEvent.type(screen.getByLabelText("Password"), "hunter2");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
}

/** Render the page with a `login` that rejects with the given backend error code. */
function renderWithLoginError(errCode: string, description: string | null = null) {
  const login = vi.fn().mockRejectedValue(new ApiError(401, "Unauthorized", description, errCode));
  return renderRoute(Route, { path: "/login", auth: { login } });
}

it("submits the credentials and lands on the home page", async () => {
  const { router, auth } = renderRoute(Route, { path: "/login" });
  await fillAndSubmit();

  await waitFor(() =>
    expect(auth.login).toHaveBeenCalledWith("alice", "hunter2", undefined, undefined),
  );
  await waitFor(() => expect(router.state.location.pathname).toBe("/"));
});

it("follows the ?next= target after signing in", async () => {
  vi.stubGlobal("location", { ...window.location, href: "" });
  renderRoute(Route, { path: "/login?next=/challenges" });
  await fillAndSubmit();

  await waitFor(() => expect(window.location.href).toBe("/challenges"));
});

it.each(["https://evil.com", "//evil.com", "javascript:alert(1)"])(
  "refuses %s as a redirect target and goes home instead",
  async (target) => {
    vi.stubGlobal("location", { ...window.location, href: "" });
    const { router } = renderRoute(Route, { path: `/login?next=${encodeURIComponent(target)}` });
    await fillAndSubmit();

    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
    expect(window.location.href).toBe("");
  },
);

it("survives the round trip from the consent page it was redirected from", async () => {
  // The consent page builds `next` from the URL the browser is actually on.
  vi.stubGlobal("location", {
    ...window.location,
    pathname: "/oauth/consent",
    search: "?client_id=app1&redirect_uri=https%3A%2F%2Fapp.example%2Fcb&state=xyz",
    href: "",
  });
  const consentUrl = window.location.pathname + window.location.search;

  const consent = renderRoute(ConsentRoute, { path: consentUrl });
  await waitFor(() => expect(consent.router.state.location.pathname).toBe("/login"));
  const redirectedTo = `/login${consent.router.state.location.searchStr}`;
  consent.unmount();

  // Hand the login page the exact URL the browser would now be sitting on.
  renderRoute(Route, { path: redirectedTo });
  await fillAndSubmit();

  await waitFor(() => expect(window.location.href).toBe(consentUrl));
});

it("shows the TOTP step when the backend asks for a code", async () => {
  renderWithLoginError("AUTH-TOTP-REQUIRED");
  await fillAndSubmit();

  expect(await screen.findByText("Two-factor authentication")).toBeDefined();
  expect(screen.queryByLabelText("Password")).toBeNull();
  // Submit stays disabled until all six digits are entered.
  expect(screen.getByRole("button", { name: "Sign in" })).toHaveProperty("disabled", true);
});

it("shows the disabled-account card", async () => {
  renderWithLoginError("AUTH-403-DISABLED");
  await fillAndSubmit();

  expect(await screen.findByText("Account Disabled")).toBeDefined();
  expect(screen.getByRole("button", { name: "Sign out" })).toBeDefined();
});

it("shows the email-verification card with a resend form", async () => {
  renderWithLoginError("AUTH-403-EMAIL-NOT-VERIFIED");
  await fillAndSubmit();

  expect(await screen.findByText("Verify your email")).toBeDefined();
  expect(screen.getByRole("button", { name: "Resend verification email" })).toBeDefined();
});

it("shows the error description for any other API error", async () => {
  renderWithLoginError("AUTH-401", "Bad username or password");
  await fillAndSubmit();

  expect(await screen.findByText("Bad username or password")).toBeDefined();
});

it("falls back to a generic message for non-API errors", async () => {
  const login = vi.fn().mockRejectedValue(new Error("boom"));
  renderRoute(Route, { path: "/login", auth: { login } });
  await fillAndSubmit();

  expect(await screen.findByText("An unexpected error occurred")).toBeDefined();
});

it("redirects an already-signed-in user away from the form", async () => {
  const { router } = renderRoute(Route, { path: "/login", auth: { user: user() } });

  await waitFor(() => expect(router.state.location.pathname).toBe("/"));
});

it("hides the sign-up link when registration is closed", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfoWith({ allow_registration: false }));
  renderRoute(Route, { path: "/login" });

  expect(await screen.findByLabelText("Username")).toBeDefined();
  expect(screen.queryByRole("link", { name: "Sign up" })).toBeNull();
});

it("lists the OAuth providers", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(
    publicInfo({ oauth_providers: [{ slug: "github", name: "GitHub", icon_url: null }] }),
  );
  renderRoute(Route, { path: "/login" });

  const link = await screen.findByRole("link", { name: "GitHub" });
  expect(link.getAttribute("href")).toContain("github");
});

it("gates submit on the captcha until the widget reports a token", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(
    publicInfo({ captcha: { enabled: true, widget_endpoint: "/api/v1/captcha/" } }),
  );
  const { container } = renderRoute(Route, { path: "/login" });

  const submit = await screen.findByRole("button", { name: "Sign in" });
  await waitFor(() => expect(submit).toHaveProperty("disabled", true));

  const widget = container.querySelector("cap-widget");
  // biome-ignore lint/style/noNonNullAssertion: rendered whenever the captcha is enabled
  widget!.dispatchEvent(new CustomEvent("solve", { detail: { token: "cap-token" } }));

  await waitFor(() => expect(submit).toHaveProperty("disabled", false));
});

it("passes the captcha token along with the credentials", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(
    publicInfo({ captcha: { enabled: true, widget_endpoint: "/api/v1/captcha/" } }),
  );
  const { container, auth } = renderRoute(Route, { path: "/login" });

  const widget = await waitFor(() => {
    const el = container.querySelector("cap-widget");
    expect(el).not.toBeNull();
    return el;
  });
  // biome-ignore lint/style/noNonNullAssertion: waitFor above rejects on null
  widget!.dispatchEvent(new CustomEvent("solve", { detail: { token: "cap-token" } }));
  await fillAndSubmit();

  await waitFor(() =>
    expect(auth.login).toHaveBeenCalledWith("alice", "hunter2", undefined, "cap-token"),
  );
});
