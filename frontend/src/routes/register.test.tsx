import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError, getPublicInfo, register } from "@/lib/api";
import { publicInfo, publicInfoWith, user } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { Route } from "./register";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getPublicInfo: vi.fn(),
  register: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));

beforeEach(() => {
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfo());
  vi.mocked(register).mockResolvedValue(undefined);
});

it("registers without an email and sends the user to the login page", async () => {
  const { router } = renderRoute(Route, { path: "/register" });

  await userEvent.type(await screen.findByLabelText("Username"), "alice");
  await userEvent.type(screen.getByLabelText("Password"), "hunter2");
  await userEvent.click(screen.getByRole("button", { name: "Sign up" }));

  await waitFor(() =>
    expect(register).toHaveBeenCalledWith({
      username: "alice",
      password: "hunter2",
      email: undefined,
      captchaToken: undefined,
    }),
  );
  expect(toast.success).toHaveBeenCalledWith("Account created. You can now sign in.");
  await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
});

it("requires the email and toasts the verification notice when the CTF demands one", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfoWith({ require_email: true }));
  renderRoute(Route, { path: "/register" });

  const email = await screen.findByLabelText("Email");
  expect(email).toHaveProperty("required", true);

  await userEvent.type(screen.getByLabelText("Username"), "alice");
  await userEvent.type(email, "alice@example.com");
  await userEvent.type(screen.getByLabelText("Password"), "hunter2");
  await userEvent.click(screen.getByRole("button", { name: "Sign up" }));

  await waitFor(() =>
    expect(register).toHaveBeenCalledWith(expect.objectContaining({ email: "alice@example.com" })),
  );
  expect(toast.success).toHaveBeenCalledWith(
    "Account created. Check your inbox to verify your email before signing in.",
  );
});

it("marks the email optional by default", async () => {
  renderRoute(Route, { path: "/register" });

  expect(await screen.findByLabelText("Email (optional)")).toHaveProperty("required", false);
});

it("redirects to the login page when registration is closed", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfoWith({ allow_registration: false }));
  const { router } = renderRoute(Route, { path: "/register" });

  await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
});

it("redirects an already-signed-in user away from the form", async () => {
  const { router } = renderRoute(Route, { path: "/register", auth: { user: user() } });

  await waitFor(() => expect(router.state.location.pathname).toBe("/"));
});

it("shows the API error description", async () => {
  vi.mocked(register).mockRejectedValue(
    new ApiError(409, "Conflict", "Username already taken", "USER-409"),
  );
  renderRoute(Route, { path: "/register" });

  await userEvent.type(await screen.findByLabelText("Username"), "alice");
  await userEvent.type(screen.getByLabelText("Password"), "hunter2");
  await userEvent.click(screen.getByRole("button", { name: "Sign up" }));

  expect(await screen.findByText("Username already taken")).toBeDefined();
});
