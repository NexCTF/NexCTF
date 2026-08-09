import { screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError, getPublicInfo, getPublishedPage } from "@/lib/api";
import { publicInfo } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { Route } from "./p.$slug";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getPublicInfo: vi.fn(),
  getPublishedPage: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfo());
});

function renderSlug(slug = "rules") {
  return renderRoute(Route, { path: `/p/${slug}`, routePath: "/p/$slug" });
}

it("loads the page named in the URL and expands magic vars", async () => {
  vi.mocked(getPublishedPage).mockResolvedValue({
    slug: "rules",
    title: "The Rules",
    content: "Welcome to {{event_name}} — and {{unknown_var}} stays put.",
    nav_placement: "nav",
  });
  renderSlug();

  expect(await screen.findByRole("heading", { name: "The Rules" })).toBeDefined();
  expect(getPublishedPage).toHaveBeenCalledWith("rules");
  expect(
    await screen.findByText(/Welcome to NexCTF — and \{\{unknown_var\}\} stays put\./),
  ).toBeDefined();
});

it("shows a not-found message for an unpublished slug", async () => {
  vi.mocked(getPublishedPage).mockRejectedValue(new ApiError(404, "Not Found"));
  renderSlug("nope");

  expect(await screen.findByText("Page not found")).toBeDefined();
});
