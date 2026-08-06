import { screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError, getPublicInfo, getPublishedPage } from "@/lib/api";
import type { AuthContext } from "@/lib/auth";
import { publicInfo, publicInfoWith, user } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { Route } from "./index";

const renderHome = (auth: Partial<AuthContext> = { user: user() }) =>
  renderRoute(Route, { path: "/", auth });

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getPublicInfo: vi.fn(),
  getPublishedPage: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfo());
  vi.mocked(getPublishedPage).mockRejectedValue(new ApiError(404, "Not Found"));
});

it("welcomes the signed-in user when no home page is configured", async () => {
  renderHome();

  expect(await screen.findByText("Welcome, player")).toBeDefined();
  expect(screen.getByRole("heading", { name: "NexCTF" })).toBeDefined();
});

it("shows the competition description", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(
    publicInfoWith({ description: "Hack all the things" }),
  );
  renderHome();

  expect(await screen.findByText("Hack all the things")).toBeDefined();
});

it("renders the custom home page instead, even for anonymous visitors", async () => {
  vi.mocked(getPublishedPage).mockResolvedValue({
    slug: "home",
    title: "Home",
    content: "# Welcome to {{event_name}}",
    nav_placement: null,
  });
  renderHome({ user: null });

  expect(await screen.findByRole("heading", { name: "Welcome to NexCTF" })).toBeDefined();
});

it("sends an anonymous visitor to the login page when there is no home page", async () => {
  const { router } = renderHome({ user: null });

  await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
});
