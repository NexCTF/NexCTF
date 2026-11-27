import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import {
  DisplayLinkDialog,
  SCREEN_TOKEN_SCOPES,
  screenTokenExpiry,
} from "@/components/display-link-dialog";
import { createMyToken, getConfig } from "@/lib/api";
import { configItem } from "@/test/fixtures";
import { renderWithRouter } from "@/test/render";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getConfig: vi.fn(),
  createMyToken: vi.fn(),
}));

const visibility = (value: string) => [configItem({ key: "visibility.scoreboard", value })];

const linkValue = () => (screen.getByLabelText("Link") as HTMLInputElement).value;

beforeEach(() => {
  vi.mocked(getConfig).mockResolvedValue(visibility("public"));
});

function renderDialog() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  renderWithRouter(
    <QueryClientProvider client={client}>
      <DisplayLinkDialog brackets={["pro", "students"]} onClose={vi.fn()} />
    </QueryClientProvider>,
  );
}

it("builds the link from the chosen settings", async () => {
  renderDialog();
  await screen.findByLabelText("Link");
  expect(linkValue()).toBe(`${window.location.origin}/display`);

  await userEvent.click(screen.getByLabelText("Show"));
  await userEvent.click(await screen.findByRole("option", { name: /each bracket in turn/ }));
  await userEvent.clear(screen.getByLabelText("Seconds per view"));
  await userEvent.type(screen.getByLabelText("Seconds per view"), "30");
  await userEvent.click(screen.getByLabelText("Screen resolution"));
  await userEvent.click(await screen.findByRole("option", { name: "4K" }));

  expect(linkValue()).toBe(`${window.location.origin}/display?rotate=30&scale=2`);
});

it("links a single bracket without rotation", async () => {
  renderDialog();

  await userEvent.click(await screen.findByLabelText("Show"));
  await userEvent.click(await screen.findByRole("option", { name: "students" }));

  expect(linkValue()).toBe(`${window.location.origin}/display?bracket=students`);
  expect(screen.queryByLabelText("Seconds per view")).toBeNull();
});

it.each([
  ["authenticated", /sign in on the screen/],
  ["hidden", /scoreboard is hidden/],
])("warns when the scoreboard visibility is %s", async (value, message) => {
  vi.mocked(getConfig).mockResolvedValue(visibility(value));
  renderDialog();

  expect(await screen.findByText(message)).toBeDefined();
});

it("adds a read-only screen token to the link, which lifts the sign-in warning", async () => {
  vi.mocked(getConfig).mockResolvedValue(visibility("authenticated"));
  vi.mocked(createMyToken).mockResolvedValue({
    id: "tok1",
    name: "Big screen",
    created_at: "",
    expires_at: null,
    last_used_at: null,
    scopes: SCREEN_TOKEN_SCOPES,
    token: "nxt_secret",
  });
  renderDialog();
  expect(await screen.findByText(/sign in on the screen/)).toBeDefined();

  await userEvent.click(screen.getByRole("button", { name: "Add a screen token" }));

  expect(await screen.findByText(/carries a read-only token/)).toBeDefined();
  expect(linkValue()).toBe(`${window.location.origin}/display#token=nxt_secret`);
  expect(createMyToken).toHaveBeenCalledWith(
    expect.stringMatching(/^Big screen/),
    ["read:scoreboard", "read:notification"],
    expect.any(String),
  );
  expect(screen.queryByText(/sign in on the screen/)).toBeNull();
});

it.each([
  ["a day after the end", "2026-12-04T10:00:00Z", "2026-12-05T10:00:00.000Z"],
  ["a day from now once the end has passed", "2026-11-01T00:00:00Z", "2026-11-28T12:00:00.000Z"],
  ["a week from now without an end time", null, "2026-12-04T12:00:00.000Z"],
])("makes a screen token expire %s", (_case, end, expected) => {
  const now = Date.parse("2026-11-27T12:00:00Z");

  expect(screenTokenExpiry(end ? new Date(end) : null, now).toISOString()).toBe(expected);
});
