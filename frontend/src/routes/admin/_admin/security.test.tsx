import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { getAdminSessionAddresses, getAdminSessionFailedLogins } from "@/lib/api";
import {
  failedLoginAddress,
  failedLoginOverview,
  failedLoginUsername,
  sessionOverview,
  sharedAddress,
  sharedAddressAccount,
} from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { Route } from "./security";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getAdminSessionAddresses: vi.fn(),
  getAdminSessionFailedLogins: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(getAdminSessionAddresses).mockResolvedValue(sessionOverview());
  vi.mocked(getAdminSessionFailedLogins).mockResolvedValue(failedLoginOverview({ addresses: [] }));
});

function render(path = "/admin/security") {
  return renderRoute(Route, { path, routePath: "/admin/security" });
}

/** The failed-login clusters live on their own tab. */
async function openFailedLogins() {
  await userEvent.click(await screen.findByRole("button", { name: "Failed logins" }));
}

/** One shared address and one address a single account is signed in from. */
function mixedOverview() {
  return sessionOverview({
    addresses: [
      sharedAddress(),
      sharedAddress({
        ip: "198.51.100.4",
        accounts: [
          sharedAddressAccount({
            user_id: "66666666-6666-4666-8666-666666666666",
            username: "carol",
          }),
        ],
      }),
    ],
  });
}

it("lists every account live on a shared address", async () => {
  render();

  expect(await screen.findByText("203.0.113.7")).toBeTruthy();
  expect(screen.getByRole("link", { name: /alice/ })).toBeTruthy();
  expect(screen.getByRole("link", { name: /bob/ })).toBeTruthy();
  expect(screen.getByText(/2 accounts/)).toBeTruthy();
});

it("flags accounts on different teams", async () => {
  vi.mocked(getAdminSessionAddresses).mockResolvedValue(
    sessionOverview({
      addresses: [
        sharedAddress({
          accounts: [
            sharedAddressAccount({
              team_id: "44444444-4444-4444-8444-444444444444",
              team_name: "Red",
            }),
            sharedAddressAccount({
              user_id: "33333333-3333-4333-8333-333333333333",
              username: "bob",
              team_id: "55555555-5555-4555-8555-555555555555",
              team_name: "Blue",
            }),
          ],
        }),
      ],
    }),
  );

  render();

  expect(await screen.findByText("Different teams")).toBeTruthy();
});

it("claims nothing about teams when both accounts are teamless", async () => {
  render();

  expect(await screen.findByText("203.0.113.7")).toBeTruthy();
  expect(screen.queryByText("Different teams")).toBeNull();
  expect(screen.queryByText("Same team")).toBeNull();
});

it("flags same-team sharing as expected instead", async () => {
  vi.mocked(getAdminSessionAddresses).mockResolvedValue(
    sessionOverview({ addresses: [sharedAddress({ same_team: true })] }),
  );

  render();

  expect(await screen.findByText("Same team")).toBeTruthy();
  expect(screen.queryByText("Different teams")).toBeNull();
});

it("marks a session that only moved to the address", async () => {
  vi.mocked(getAdminSessionAddresses).mockResolvedValue(
    sessionOverview({
      addresses: [
        sharedAddress({
          accounts: [
            sharedAddressAccount({ opened_here: false }),
            sharedAddressAccount({
              user_id: "33333333-3333-4333-8333-333333333333",
              username: "bob",
            }),
          ],
        }),
      ],
    }),
  );

  render();

  expect(await screen.findByText("Moved here")).toBeTruthy();
});

it("leaves single-account addresses out of the default listing", async () => {
  vi.mocked(getAdminSessionAddresses).mockResolvedValue(mixedOverview());

  render();

  expect(await screen.findByText("203.0.113.7")).toBeTruthy();
  expect(screen.queryByText("198.51.100.4")).toBeNull();
});

it("says how many addresses the shared filter is hiding", async () => {
  vi.mocked(getAdminSessionAddresses).mockResolvedValue(mixedOverview());

  render();

  expect(await screen.findByText(/showing 1 of 2 addresses/i)).toBeTruthy();
});

it("shows every address on request", async () => {
  vi.mocked(getAdminSessionAddresses).mockResolvedValue(mixedOverview());

  render();
  await userEvent.click(await screen.findByRole("button", { name: /show every address/i }));

  expect(await screen.findByText("198.51.100.4")).toBeTruthy();
  expect(screen.getByText("203.0.113.7")).toBeTruthy();
});

it("finds a single-account address once it is searched for", async () => {
  vi.mocked(getAdminSessionAddresses).mockResolvedValue(mixedOverview());

  render();
  await screen.findByText("203.0.113.7");
  await userEvent.type(screen.getByRole("textbox", { name: /search an address/i }), "198.51");

  expect(await screen.findByText("198.51.100.4")).toBeTruthy();
  expect(screen.queryByText("203.0.113.7")).toBeNull();
});

it("says so when a searched address has nothing live on it", async () => {
  render();
  await screen.findByText("203.0.113.7");
  await userEvent.type(screen.getByRole("textbox", { name: /search an address/i }), "10.0.0.1");

  expect(await screen.findByText(/no live session comes from an address/i)).toBeTruthy();
});

it("keeps the totals on every live session, not only the listed ones", async () => {
  vi.mocked(getAdminSessionAddresses).mockResolvedValue(
    sessionOverview({ session_count: 12, account_count: 9, address_count: 7 }),
  );

  render();

  expect(await screen.findByText("12")).toBeTruthy();
  expect(screen.getByText("9")).toBeTruthy();
  expect(screen.getByText("7")).toBeTruthy();
});

it("says so when nothing is shared", async () => {
  vi.mocked(getAdminSessionAddresses).mockResolvedValue(
    sessionOverview({
      addresses: [sharedAddress({ ip: "198.51.100.4", accounts: [sharedAddressAccount()] })],
    }),
  );

  render();

  expect(await screen.findByText(/no address has more than one account/i)).toBeTruthy();
});

it("says so when no one is signed in at all", async () => {
  vi.mocked(getAdminSessionAddresses).mockResolvedValue(sessionOverview({ addresses: [] }));

  render();

  expect(await screen.findByText(/no one is signed in/i)).toBeTruthy();
});

it("asks the API for the window the admin picked", async () => {
  render();
  await screen.findByText("203.0.113.7");
  await userEvent.click(screen.getByRole("button", { name: /last 24 hours/i }));

  expect(vi.mocked(getAdminSessionAddresses)).toHaveBeenLastCalledWith("day");
});

it("counts logins rather than live sessions outside live mode", async () => {
  vi.mocked(getAdminSessionAddresses).mockResolvedValue(sessionOverview({ session_count: 12 }));

  render();
  await userEvent.click(await screen.findByRole("button", { name: /whole event/i }));

  expect(await screen.findByText("Logins")).toBeTruthy();
  expect(screen.queryByText("Live sessions")).toBeNull();
});

it("counts an account's logins on an address it signed in from", async () => {
  vi.mocked(getAdminSessionAddresses).mockResolvedValue(
    sessionOverview({
      addresses: [
        sharedAddress({
          accounts: [
            sharedAddressAccount({ session_count: 3, user_agent: null }),
            sharedAddressAccount({
              user_id: "33333333-3333-4333-8333-333333333333",
              username: "bob",
            }),
          ],
        }),
      ],
    }),
  );

  render();
  await userEvent.click(await screen.findByRole("button", { name: /whole event/i }));

  expect(await screen.findByText(/3 logins/)).toBeTruthy();
});

it("says so when the window recorded no login", async () => {
  vi.mocked(getAdminSessionAddresses).mockResolvedValue(sessionOverview({ addresses: [] }));

  render();
  await userEvent.click(await screen.findByRole("button", { name: /whole event/i }));

  expect(await screen.findByText(/no login was recorded/i)).toBeTruthy();
});

it("groups failed logins by the address they came from", async () => {
  vi.mocked(getAdminSessionFailedLogins).mockResolvedValue(
    failedLoginOverview({
      addresses: [
        failedLoginAddress({
          usernames: [
            failedLoginUsername({ username: "root", attempt_count: 7 }),
            failedLoginUsername({ username: "admin" }),
          ],
        }),
      ],
    }),
  );

  render();
  await openFailedLogins();

  expect(await screen.findByText("203.0.113.9")).toBeTruthy();
  expect(screen.getByText("2 usernames")).toBeTruthy();
  expect(screen.getByText("root")).toBeTruthy();
  expect(screen.getByText("(7)")).toBeTruthy();
});

it("links a rejected username that matches an account", async () => {
  vi.mocked(getAdminSessionFailedLogins).mockResolvedValue(
    failedLoginOverview({
      addresses: [
        failedLoginAddress({
          usernames: [
            failedLoginUsername({
              username: "dave",
              user_id: "22222222-2222-4222-8222-222222222222",
            }),
            failedLoginUsername({ username: "root" }),
          ],
        }),
      ],
    }),
  );

  render();
  await openFailedLogins();

  expect(await screen.findByRole("link", { name: "dave" })).toBeTruthy();
  expect(screen.queryByRole("link", { name: "root" })).toBeNull();
});

it("leaves an address that tried a single username out until asked", async () => {
  vi.mocked(getAdminSessionFailedLogins).mockResolvedValue(
    failedLoginOverview({
      addresses: [
        failedLoginAddress({
          ip: "198.51.100.60",
          usernames: [failedLoginUsername({ username: "root", attempt_count: 9 })],
        }),
      ],
    }),
  );

  render();
  await openFailedLogins();
  expect(await screen.findByText(/no address tried more than one username/i)).toBeTruthy();

  await userEvent.click(screen.getByRole("button", { name: /show every failing address/i }));

  expect(await screen.findByText("198.51.100.60")).toBeTruthy();
});

it("starts the failed-login tab at 24 hours and never asks for live", async () => {
  render();
  await openFailedLogins();
  expect(vi.mocked(getAdminSessionFailedLogins)).toHaveBeenLastCalledWith("day");
  expect(screen.queryByRole("button", { name: /live now/i })).toBeNull();

  await userEvent.click(screen.getByRole("button", { name: /whole event/i }));

  expect(vi.mocked(getAdminSessionFailedLogins)).toHaveBeenLastCalledWith("all");
});

it("says so when nothing failed in the window", async () => {
  render();
  await openFailedLogins();

  expect(await screen.findByText(/no failed login in this window/i)).toBeTruthy();
});

it("opens the tab named in the URL", async () => {
  vi.mocked(getAdminSessionFailedLogins).mockResolvedValue(failedLoginOverview());

  render("/admin/security?tab=failed-logins");

  expect(await screen.findByText("203.0.113.9")).toBeTruthy();
  expect(screen.queryByText("203.0.113.7")).toBeNull();
});

it("leaves the sessions tab open for an unknown tab", async () => {
  render("/admin/security?tab=nonsense");

  expect(await screen.findByText("203.0.113.7")).toBeTruthy();
});

it("marks the page as beta", async () => {
  render();

  expect(await screen.findByText("Beta")).toBeTruthy();
});
