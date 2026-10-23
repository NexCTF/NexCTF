import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError, createFirstAdmin, getConfig, getSetupStatus, updateConfig } from "@/lib/api";
import type { AuthContext } from "@/lib/auth";
import { configItem, user } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { Route } from "./setup";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  createFirstAdmin: vi.fn(),
  getConfig: vi.fn(),
  getSetupStatus: vi.fn(),
  updateConfig: vi.fn(),
}));

const admin = user({ role: "admin", username: "root" });

beforeEach(() => {
  vi.mocked(getSetupStatus).mockResolvedValue({ admin_required: true });
  vi.mocked(createFirstAdmin).mockResolvedValue(undefined);
  vi.mocked(getConfig).mockResolvedValue([
    configItem({ key: "ctf.name", label: "Event name", value: "NexCTF" }),
    configItem({ key: "ctf.freeze_time", label: "Freeze time" }),
  ]);
  vi.mocked(updateConfig).mockResolvedValue([]);
});

/** Render a step of a setup whose admin already exists. */
function renderStep(step: string, auth: Partial<AuthContext> = { user: admin }) {
  vi.mocked(getSetupStatus).mockResolvedValue({ admin_required: false });
  return renderRoute(Route, { path: `/setup?step=${step}`, auth });
}

async function fillAccount(password = "strongpass", confirm = password) {
  await userEvent.type(await screen.findByLabelText("Username"), "root");
  await userEvent.type(screen.getByLabelText("Password"), password);
  await userEvent.type(screen.getByLabelText("Confirm password"), confirm);
  await userEvent.click(screen.getByRole("button", { name: "Create the account" }));
}

it("creates the admin with the link token, then moves to the event step", async () => {
  const { auth, router } = renderRoute(Route, {
    path: "/setup?token=tok123",
    auth: { user: admin },
  });
  expect(screen.queryByLabelText("Setup token")).toBeNull();

  await fillAccount();

  expect(createFirstAdmin).toHaveBeenCalledWith({
    token: "tok123",
    username: "root",
    password: "strongpass",
    email: undefined,
  });
  expect(auth.refresh).toHaveBeenCalled();
  expect(await screen.findByText("Your event")).toBeDefined();
  expect(router.state.location.search).toEqual({ step: "event" });
});

it("asks for the token when the link has none", async () => {
  renderRoute(Route, { path: "/setup" });

  expect(await screen.findByLabelText("Setup token")).toBeDefined();
});

it("refuses mismatched passwords without calling the API", async () => {
  renderRoute(Route, { path: "/setup?token=tok123" });
  await fillAccount("strongpass", "otherpass");

  expect(await screen.findByText("Passwords do not match")).toBeDefined();
  expect(createFirstAdmin).not.toHaveBeenCalled();
});

it("explains a stale token and lets the admin paste a new one", async () => {
  vi.mocked(createFirstAdmin).mockRejectedValue(
    new ApiError(403, "Forbidden", null, "SETUP-403-TOKEN"),
  );
  renderRoute(Route, { path: "/setup?token=old" });
  await fillAccount();

  expect(await screen.findByText(/This setup token is not valid anymore/)).toBeDefined();
  expect(screen.getByLabelText("Setup token")).toBeDefined();
});

it("saves only the event settings that changed", async () => {
  renderStep("event");

  const name = await screen.findByDisplayValue("NexCTF");
  expect(screen.getByText("Event name")).toBeDefined();
  expect(screen.queryByText("Freeze time")).toBeNull();
  await userEvent.clear(name);
  await userEvent.type(name, "Spring CTF");
  await userEvent.click(screen.getByRole("button", { name: "Save and continue" }));

  expect(updateConfig).toHaveBeenCalledWith({ "ctf.name": "Spring CTF" });
  expect(await screen.findByText("You are all set")).toBeDefined();
});

it("lists the next steps with links into the admin", async () => {
  renderStep("next");

  const link = await screen.findByRole("link", { name: /Create a challenge/ });
  expect(link.getAttribute("href")).toBe("/admin/challenges");
  expect(screen.getByRole("link", { name: /Set up email/ }).getAttribute("href")).toBe(
    "/admin/settings?category=email",
  );
});

it("sends visitors away once an admin exists", async () => {
  const { router } = renderStep("event", { user: null });

  await waitFor(() => expect(router.state.location.pathname).toBe("/"));
});

it("moves on without saving when a field is set back to its value", async () => {
  renderStep("event");

  const name = await screen.findByDisplayValue("NexCTF");
  await userEvent.type(name, "!");
  await userEvent.type(name, "{Backspace}");
  await userEvent.click(screen.getByRole("button", { name: "Save and continue" }));

  expect(await screen.findByText("You are all set")).toBeDefined();
  expect(updateConfig).not.toHaveBeenCalled();
});

it("offers a language switch", async () => {
  renderRoute(Route, { path: "/setup?token=tok123" });

  expect(await screen.findByRole("button", { name: "Change language" })).toBeDefined();
});
