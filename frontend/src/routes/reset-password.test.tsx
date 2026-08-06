import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError, resetPassword } from "@/lib/api";
import { renderRoute } from "@/test/render";
import { Route } from "./reset-password";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  resetPassword: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(resetPassword).mockResolvedValue(undefined);
});

async function submit(password: string, confirm: string) {
  await userEvent.type(await screen.findByLabelText("New password"), password);
  await userEvent.type(screen.getByLabelText("Confirm password"), confirm);
  await userEvent.click(screen.getByRole("button", { name: "Reset password" }));
}

it("rejects the link when the token is missing", async () => {
  renderRoute(Route, { path: "/reset-password" });

  expect(await screen.findByText("Invalid link")).toBeDefined();
  expect(screen.queryByLabelText("New password")).toBeNull();
});

it("sets the new password with the token from the URL", async () => {
  renderRoute(Route, { path: "/reset-password?token=tok123" });
  await submit("hunter2", "hunter2");

  expect(resetPassword).toHaveBeenCalledWith("tok123", "hunter2");
  expect(await screen.findByText("Password updated")).toBeDefined();
});

it("refuses mismatched passwords without calling the API", async () => {
  renderRoute(Route, { path: "/reset-password?token=tok123" });
  await submit("hunter2", "hunter3");

  expect(await screen.findByText("Passwords do not match")).toBeDefined();
  expect(resetPassword).not.toHaveBeenCalled();
});

it("explains an expired token", async () => {
  vi.mocked(resetPassword).mockRejectedValue(
    new ApiError(400, "Bad Request", null, "AUTH-400-RESET-TOKEN"),
  );
  renderRoute(Route, { path: "/reset-password?token=tok123" });
  await submit("hunter2", "hunter2");

  expect(await screen.findByText("This reset link is invalid or has expired.")).toBeDefined();
});

it("falls back to a generic message for other failures", async () => {
  vi.mocked(resetPassword).mockRejectedValue(new Error("boom"));
  renderRoute(Route, { path: "/reset-password?token=tok123" });
  await submit("hunter2", "hunter2");

  expect(await screen.findByText("An unexpected error occurred")).toBeDefined();
});
