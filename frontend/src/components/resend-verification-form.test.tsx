import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { beforeEach, expect, it, vi } from "vitest";
import { resendVerification } from "@/lib/api";
import { ResendVerificationForm } from "./resend-verification-form";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  resendVerification: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));

beforeEach(() => {
  vi.mocked(resendVerification).mockResolvedValue(undefined);
});

async function submit() {
  await userEvent.type(screen.getByLabelText("Email"), "alice@example.com");
  await userEvent.click(screen.getByRole("button", { name: "Resend verification email" }));
}

it("re-sends the verification email", async () => {
  render(<ResendVerificationForm />);
  await submit();

  expect(resendVerification).toHaveBeenCalledWith("alice@example.com");
  await waitFor(() =>
    expect(toast.success).toHaveBeenCalledWith(
      "If that email needs verification, a new link is on its way.",
    ),
  );
});

it("toasts an error when the request fails", async () => {
  vi.mocked(resendVerification).mockRejectedValue(new Error("boom"));
  render(<ResendVerificationForm />);
  await submit();

  await waitFor(() => expect(toast.error).toHaveBeenCalledWith("An unexpected error occurred"));
});
