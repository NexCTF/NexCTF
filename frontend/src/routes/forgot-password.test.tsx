import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError, forgotPassword } from "@/lib/api";
import { user } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { Route } from "./forgot-password";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  forgotPassword: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(forgotPassword).mockResolvedValue(undefined);
});

async function submit(email = "alice@example.com") {
  await userEvent.type(await screen.findByLabelText("Email"), email);
  await userEvent.click(screen.getByRole("button", { name: "Send reset link" }));
}

it("sends the reset link and confirms without leaking whether the account exists", async () => {
  renderRoute(Route, { path: "/forgot-password" });
  await submit();

  expect(forgotPassword).toHaveBeenCalledWith("alice@example.com");
  expect(await screen.findByText("Check your email")).toBeDefined();
});

it("shows a generic error when the request fails", async () => {
  vi.mocked(forgotPassword).mockRejectedValue(
    new ApiError(429, "Too Many Requests", "Slow down", "RATE-429"),
  );
  renderRoute(Route, { path: "/forgot-password" });
  await submit();

  expect(await screen.findByText("An unexpected error occurred")).toBeDefined();
});

it("redirects an already-signed-in user away from the form", async () => {
  const { router } = renderRoute(Route, { path: "/forgot-password", auth: { user: user() } });

  await waitFor(() => expect(router.state.location.pathname).toBe("/"));
});
