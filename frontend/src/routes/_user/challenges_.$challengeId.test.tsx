import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { beforeEach, expect, it, vi } from "vitest";
import { getChallenge, getPublicInfo, submitAnswer, unlockHint } from "@/lib/api";
import type { AuthContext } from "@/lib/auth";
import { challengeDetail, publicInfo, question, user } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { Route } from "./challenges_.$challengeId";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getPublicInfo: vi.fn(),
  getChallenge: vi.fn(),
  submitAnswer: vi.fn(),
  unlockHint: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));

beforeEach(() => {
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfo());
  vi.mocked(getChallenge).mockResolvedValue(challengeDetail());
});

function renderChallenge(auth: Partial<AuthContext> = { user: user() }) {
  return renderRoute(Route, {
    path: "/challenges/c1",
    routePath: "/challenges/$challengeId",
    auth,
  });
}

it("shows the challenge with its category, tags and progress", async () => {
  vi.mocked(getChallenge).mockResolvedValue(
    challengeDetail({ tags: ["rsa"], question_count: 4, solved_count: 1, sequential: true }),
  );
  renderChallenge();

  expect(await screen.findByRole("heading", { name: "Baby RSA" })).toBeDefined();
  expect(screen.getByText("crypto")).toBeDefined();
  expect(screen.getByText("Sequential")).toBeDefined();
  expect(screen.getByText("1/4 questions solved")).toBeDefined();
  expect(screen.getByText("25%")).toBeDefined();
});

it("submits a typed answer and reports a correct solve", async () => {
  vi.mocked(submitAnswer).mockResolvedValue({
    is_correct: true,
    already_solved: false,
    points_earned: 100,
    message: "Correct!",
  });
  renderChallenge();

  await userEvent.type(await screen.findByPlaceholderText("Enter your answer…"), "flag_x");
  await userEvent.click(screen.getByRole("button", { name: "Submit" }));

  await waitFor(() => expect(submitAnswer).toHaveBeenCalledWith("c1", "q1", "flag_x"));
  expect(toast.success).toHaveBeenCalledWith("Correct!");
});

it("reports a wrong answer without clearing the field", async () => {
  vi.mocked(submitAnswer).mockResolvedValue({
    is_correct: false,
    already_solved: false,
    points_earned: 0,
    message: "Nope",
  });
  renderChallenge();

  const input = await screen.findByPlaceholderText("Enter your answer…");
  await userEvent.type(input, "wrong");
  await userEvent.click(screen.getByRole("button", { name: "Submit" }));

  await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Nope"));
  expect(input).toHaveProperty("value", "wrong");
});

it("keeps submit disabled while the answer is blank", async () => {
  renderChallenge();

  expect(await screen.findByRole("button", { name: "Submit" })).toHaveProperty("disabled", true);
});

it("sends multi-select answers as a sorted JSON array", async () => {
  vi.mocked(getChallenge).mockResolvedValue(
    challengeDetail({
      questions: [
        question({ input_type: "mcq", multi_select: true, options: ["charlie", "alpha", "bravo"] }),
      ],
    }),
  );
  vi.mocked(submitAnswer).mockResolvedValue({
    is_correct: true,
    already_solved: false,
    points_earned: 10,
    message: "ok",
  });
  renderChallenge();

  await userEvent.click(await screen.findByRole("checkbox", { name: "charlie" }));
  await userEvent.click(screen.getByRole("checkbox", { name: "alpha" }));
  await userEvent.click(screen.getByRole("button", { name: "Submit" }));

  await waitFor(() =>
    expect(submitAnswer).toHaveBeenCalledWith("c1", "q1", JSON.stringify(["alpha", "charlie"])),
  );
});

it("hides the details of a locked question", async () => {
  vi.mocked(getChallenge).mockResolvedValue(
    challengeDetail({
      questions: [question({ is_locked: true, label: "Step 2", points: 50, malus: 10 })],
    }),
  );
  renderChallenge();

  expect(await screen.findByText("Step 2")).toBeDefined();
  expect(screen.getByText("50 pts / −10")).toBeDefined();
  expect(screen.queryByRole("button", { name: "Submit" })).toBeNull();
});

it("replaces the form with a solved marker", async () => {
  vi.mocked(getChallenge).mockResolvedValue(
    challengeDetail({ questions: [question({ is_solved: true })] }),
  );
  renderChallenge();

  await userEvent.click(await screen.findByText("What is the flag?"));

  expect(screen.getByText("✓ Solved")).toBeDefined();
  expect(screen.queryByRole("button", { name: "Submit" })).toBeNull();
});

it("asks for confirmation before spending points on a hint", async () => {
  vi.mocked(getChallenge).mockResolvedValue(
    challengeDetail({
      questions: [
        question({
          hints: [{ id: "h1", title: "Nudge", cost: 25, is_unlocked: false, content: null }],
        }),
      ],
    }),
  );
  vi.mocked(unlockHint).mockResolvedValue(undefined as never);
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
  renderChallenge();

  await userEvent.click(await screen.findByRole("button", { name: "−25 pts" }));

  expect(confirmSpy).toHaveBeenCalledWith("Unlock this hint for 25 points?");
  expect(unlockHint).not.toHaveBeenCalled();

  confirmSpy.mockReturnValue(true);
  await userEvent.click(screen.getByRole("button", { name: "−25 pts" }));
  await waitFor(() => expect(unlockHint).toHaveBeenCalledWith("c1", "q1", "h1"));
});

it("unlocks a free hint without confirmation and shows its content once unlocked", async () => {
  vi.mocked(getChallenge).mockResolvedValue(
    challengeDetail({
      questions: [
        question({
          hints: [{ id: "h1", title: "Nudge", cost: 0, is_unlocked: true, content: "Try base64" }],
        }),
      ],
    }),
  );
  renderChallenge();

  expect(await screen.findByText("Try base64")).toBeDefined();
  expect(screen.queryByRole("button", { name: "Unlock" })).toBeNull();
});

it("sends an anonymous visitor to the login page", async () => {
  const { router } = renderChallenge({ user: null });

  await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
  expect(getChallenge).not.toHaveBeenCalled();
});
