import { screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { getAdminStats } from "@/lib/api";
import { user } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { Route } from "./_admin";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getAdminStats: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));

beforeEach(() => {
  vi.mocked(getAdminStats).mockRejectedValue(new Error("not needed"));
});

it("sends a signed-out visitor to the login page", async () => {
  const { router } = renderRoute(Route, {
    path: "/admin",
    routePath: "/admin",
    auth: { user: null, isLoading: false },
  });

  await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
});

it("waits for the identity before deciding", () => {
  const { router } = renderRoute(Route, {
    path: "/admin",
    routePath: "/admin",
    auth: { user: null, isLoading: true },
  });

  expect(router.state.location.pathname).toBe("/admin");
});

it("renders the panel for a signed-in admin", async () => {
  renderRoute(Route, {
    path: "/admin",
    routePath: "/admin",
    auth: { user: user({ role: "admin" }), isLoading: false },
  });

  expect(await screen.findByText("Admin")).toBeTruthy();
});

it("groups the read-only views under Audit", async () => {
  renderRoute(Route, {
    path: "/admin",
    routePath: "/admin",
    auth: { user: user({ role: "admin" }), isLoading: false },
  });

  expect(await screen.findByText("Audit")).toBeTruthy();
  expect(screen.getByRole("link", { name: "Events" })).toBeTruthy();
  expect(screen.getByRole("link", { name: /Security/ })).toBeTruthy();
});
