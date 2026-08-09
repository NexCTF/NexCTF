import { screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { verifyEmail } from "@/lib/api";
import { renderRoute } from "@/test/render";
import { Route } from "./verify-email";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  verifyEmail: vi.fn(),
  resendVerification: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(verifyEmail).mockResolvedValue(undefined);
});

it("confirms the address with the token from the URL", async () => {
  renderRoute(Route, { path: "/verify-email?token=tok123" });

  expect(await screen.findByText("Email verified")).toBeDefined();
  expect(verifyEmail).toHaveBeenCalledWith("tok123");
  expect(verifyEmail).toHaveBeenCalledTimes(1);
});

it("offers a resend form when the token is rejected", async () => {
  vi.mocked(verifyEmail).mockRejectedValue(new Error("expired"));
  renderRoute(Route, { path: "/verify-email?token=tok123" });

  expect(await screen.findByText("Verification failed")).toBeDefined();
  expect(screen.getByRole("button", { name: "Resend verification email" })).toBeDefined();
});

it("skips the API call entirely when no token is present", async () => {
  renderRoute(Route, { path: "/verify-email" });

  expect(await screen.findByText("Verification failed")).toBeDefined();
  expect(verifyEmail).not.toHaveBeenCalled();
});
