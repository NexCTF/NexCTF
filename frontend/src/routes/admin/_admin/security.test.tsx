import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import {
  getAdminSessionAddresses,
  getAdminSessionClients,
  getAdminSessionClientsSummary,
  getAdminSessionFailedLogins,
} from "@/lib/api";
import {
  clientSighting,
  clientSummary,
  failedLoginAddress,
  failedLoginOverview,
  failedLoginUsername,
  paginated,
  sessionOverview,
  sharedAddress,
  sharedAddressAccount,
} from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { Route } from "./security";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getAdminSessionAddresses: vi.fn(),
  getAdminSessionClients: vi.fn(),
  getAdminSessionClientsSummary: vi.fn(),
  getAdminSessionFailedLogins: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(getAdminSessionAddresses).mockResolvedValue(sessionOverview());
  vi.mocked(getAdminSessionFailedLogins).mockResolvedValue(failedLoginOverview({ addresses: [] }));
  vi.mocked(getAdminSessionClients).mockResolvedValue(paginated([]));
  vi.mocked(getAdminSessionClientsSummary).mockResolvedValue(clientSummary());
});

function render(path = "/admin/security") {
  return renderRoute(Route, { path, routePath: "/admin/security" });
}

/** The failed-login clusters live on their own tab. */
async function openFailedLogins() {
  await userEvent.click(await screen.findByRole("tab", { name: "Failed logins" }));
}

/** A single-account address listed before a shared one. */
function mixedOverview() {
  return sessionOverview({
    addresses: [
      sharedAddress({
        ip: "198.51.100.4",
        accounts: [
          sharedAddressAccount({
            user_id: "66666666-6666-4666-8666-666666666666",
            username: "carol",
          }),
        ],
      }),
      sharedAddress(),
    ],
  });
}

/** The addresses in the order the table lists them. */
function listedAddresses(): string[] {
  return screen.getAllByText(/^\d+\.\d+\.\d+\.\d+$/).map((cell) => cell.textContent ?? "");
}

async function search(text: string) {
  await userEvent.type(screen.getByPlaceholderText("Search…"), text);
}

/** Tick one value of a table filter, then close the menu to apply it. */
async function pickFilter(trigger: string, option: string) {
  await userEvent.click(screen.getByText(trigger));
  await userEvent.click(await screen.findByRole("menuitemcheckbox", { name: option }));
  await userEvent.keyboard("{Escape}");
}

it("lists every account live on a shared address", async () => {
  render();

  expect(await screen.findByText("203.0.113.7")).toBeTruthy();
  expect(screen.getByRole("link", { name: /alice/ })).toBeTruthy();
  expect(screen.getByRole("link", { name: /bob/ })).toBeTruthy();
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

it("lists shared addresses before single-account ones", async () => {
  vi.mocked(getAdminSessionAddresses).mockResolvedValue(mixedOverview());

  render();
  await screen.findByText("203.0.113.7");

  expect(listedAddresses()).toEqual(["203.0.113.7", "198.51.100.4"]);
});

it("narrows the list to shared addresses on request", async () => {
  vi.mocked(getAdminSessionAddresses).mockResolvedValue(mixedOverview());

  render();
  await screen.findByText("198.51.100.4");
  await pickFilter("Accounts: All", "Shared");

  await waitFor(() => expect(screen.queryByText("198.51.100.4")).toBeNull());
  expect(screen.getByText("Accounts: Shared")).toBeTruthy();
  expect(screen.getByText("203.0.113.7")).toBeTruthy();
});

it("finds an address by its IP or by an account on it", async () => {
  vi.mocked(getAdminSessionAddresses).mockResolvedValue(mixedOverview());

  render();
  await screen.findByText("203.0.113.7");
  await search("carol");

  await waitFor(() => expect(screen.queryByText("203.0.113.7")).toBeNull());
  expect(screen.getByText("198.51.100.4")).toBeTruthy();
});

it("says so when a searched address has nothing live on it", async () => {
  render();
  await screen.findByText("203.0.113.7");
  await search("10.0.0.1");

  expect(await screen.findByText("No results found.")).toBeTruthy();
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

  expect((await screen.findAllByText("Logins")).length).toBeGreaterThan(0);
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

  expect(await screen.findByTitle(/3 logins/)).toBeTruthy();
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

it("lists addresses that tried several usernames first", async () => {
  vi.mocked(getAdminSessionFailedLogins).mockResolvedValue(
    failedLoginOverview({
      addresses: [
        failedLoginAddress({
          ip: "198.51.100.60",
          attempt_count: 30,
          username_count: 1,
          usernames: [failedLoginUsername({ username: "root", attempt_count: 30 })],
        }),
        failedLoginAddress({ username_count: 2 }),
      ],
    }),
  );

  render();
  await openFailedLogins();
  await screen.findByText("198.51.100.60");

  expect(listedAddresses()).toEqual(["203.0.113.9", "198.51.100.60"]);
});

it("narrows failed logins to the ones matching an account", async () => {
  vi.mocked(getAdminSessionFailedLogins).mockResolvedValue(
    failedLoginOverview({
      addresses: [
        failedLoginAddress({ ip: "198.51.100.60", known_username_count: 0 }),
        failedLoginAddress({ known_username_count: 1 }),
      ],
    }),
  );

  render();
  await openFailedLogins();
  await screen.findByText("198.51.100.60");
  await pickFilter("Known accounts: All", "Matches an account");

  await waitFor(() => expect(screen.queryByText("198.51.100.60")).toBeNull());
  expect(screen.getByText("203.0.113.9")).toBeTruthy();
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

  expect(await screen.findByText("No results found.")).toBeTruthy();
});

it("counts the usernames the server left off the list", async () => {
  vi.mocked(getAdminSessionFailedLogins).mockResolvedValue(
    failedLoginOverview({
      addresses: [
        failedLoginAddress({
          username_count: 25,
          usernames: [
            failedLoginUsername({ user_id: "u-1" }),
            failedLoginUsername(),
            failedLoginUsername({ username: "bob" }),
          ],
        }),
      ],
    }),
  );
  render();
  await openFailedLogins();

  expect(await screen.findByText("+23 more")).toBeTruthy();
});

it("opens the tab named in the URL", async () => {
  vi.mocked(getAdminSessionFailedLogins).mockResolvedValue(failedLoginOverview());

  render("/admin/security?tab=failed-logins");

  expect(await screen.findByText("203.0.113.9")).toBeTruthy();
  expect(screen.queryByText("203.0.113.7")).toBeNull();
});

it("exposes the views as tabs and marks the open one selected", async () => {
  render();

  const sessions = await screen.findByRole("tab", { name: "Sessions" });
  expect(sessions.getAttribute("aria-selected")).toBe("true");

  await openFailedLogins();

  expect(screen.getByRole("tab", { name: "Failed logins" }).getAttribute("aria-selected")).toBe(
    "true",
  );
  expect(sessions.getAttribute("aria-selected")).toBe("false");
  expect(screen.getByRole("tabpanel")).toBeTruthy();
});

it("leaves the sessions tab open for an unknown tab", async () => {
  render("/admin/security?tab=nonsense");

  expect(await screen.findByText("203.0.113.7")).toBeTruthy();
});

it("marks the page as beta", async () => {
  render();

  expect(await screen.findByText("Beta")).toBeTruthy();
});

/** The user-agent report lives on its own tab. */
async function openClients() {
  await userEvent.click(await screen.findByRole("tab", { name: "Clients" }));
}

const AI_UA = "Mozilla/5.0 (compatible; Claude-User/1.0)";

it("lists who used which client, naming the token", async () => {
  vi.mocked(getAdminSessionClients).mockResolvedValue(
    paginated([
      clientSighting({
        user_agent: AI_UA,
        category: "ai",
        team_id: "44444444-4444-4444-8444-444444444444",
        team_name: "Red",
      }),
      clientSighting({
        id: "66666666-6666-4666-8666-666666666666",
        user_id: "33333333-3333-4333-8333-333333333333",
        username: "bob",
        source: "token",
        token_name: "solver",
      }),
    ]),
  );
  render();
  await openClients();

  expect(await screen.findByText(AI_UA)).toBeTruthy();
  expect(screen.getByText("AI")).toBeTruthy();
  expect(screen.getByRole("link", { name: /Red/ })).toBeTruthy();
  expect(screen.getByRole("link", { name: /bob/ })).toBeTruthy();
  expect(screen.getByText("API token: solver")).toBeTruthy();
});

it("starts unfiltered over 24 hours", async () => {
  render();
  await openClients();

  await screen.findByText("No results found.");
  expect(getAdminSessionClients).toHaveBeenCalledWith(
    "day",
    expect.not.stringContaining("category="),
  );
  expect(getAdminSessionClientsSummary).toHaveBeenCalledWith("day");
  expect(screen.queryByRole("button", { name: "Live now" })).toBeNull();
});

it("filters clients by category under readable names", async () => {
  vi.mocked(getAdminSessionClients).mockResolvedValue({
    ...paginated([clientSighting()]),
    filter_attributes: { category: ["ai", "automation", "browser"], source: ["cookie", "token"] },
  });
  render();
  await openClients();

  expect(await screen.findByText("Source: All")).toBeTruthy();
  await pickFilter("Category: All", "AI");

  expect(await screen.findByText("Category: AI")).toBeTruthy();
  expect(getAdminSessionClients).toHaveBeenLastCalledWith(
    "day",
    expect.stringContaining("category=ai"),
  );
});

it("reloads both the table and the counts for the whole event", async () => {
  render();
  await openClients();
  await screen.findByText("No results found.");

  await userEvent.click(screen.getByRole("button", { name: "Whole event" }));

  expect(getAdminSessionClients).toHaveBeenLastCalledWith("all", expect.any(String));
  expect(getAdminSessionClientsSummary).toHaveBeenLastCalledWith("all");
});

it("shows how many accounts used AI clients", async () => {
  vi.mocked(getAdminSessionClientsSummary).mockResolvedValue(
    clientSummary({ account_count: 12, ai_account_count: 3 }),
  );
  render();
  await openClients();

  const card = (await screen.findByText("Accounts on AI clients")).parentElement;
  expect(card?.textContent).toContain("3");
});
