import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { beforeEach, expect, it, vi } from "vitest";
import { getChallenge, getPublicInfo, submitAnswer, submitFeedback, unlockHint } from "@/lib/api";
import type { AuthContext } from "@/lib/auth";
import { challengeDetail, publicInfo, publicInfoWith, question, user } from "@/test/fixtures";
import { clickAndCancel, clickAndConfirm, renderRoute } from "@/test/render";
import { Route } from "./challenges_.$challengeId";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getPublicInfo: vi.fn(),
  getChallenge: vi.fn(),
  submitAnswer: vi.fn(),
  submitFeedback: vi.fn(),
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
    is_blocked: false,
    is_correct: true,
    already_solved: false,
    points_earned: 100,
  });
  renderChallenge();

  await userEvent.type(await screen.findByPlaceholderText("Enter your answer…"), "flag_x");
  await userEvent.click(screen.getByRole("button", { name: "Submit" }));

  await waitFor(() => expect(submitAnswer).toHaveBeenCalledWith("c1", "q1", "flag_x"));
  expect(toast.success).toHaveBeenCalledWith("Correct! 🎉");
});

it("reports a wrong answer without clearing the field", async () => {
  vi.mocked(submitAnswer).mockResolvedValue({
    is_blocked: false,
    is_correct: false,
    already_solved: false,
    points_earned: 0,
  });
  renderChallenge();

  const input = await screen.findByPlaceholderText("Enter your answer…");
  await userEvent.type(input, "wrong");
  await userEvent.click(screen.getByRole("button", { name: "Submit" }));

  await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Wrong answer, try again."));
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
    is_blocked: false,
    is_correct: true,
    already_solved: false,
    points_earned: 10,
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
  expect(screen.getByText("50 pts")).toBeDefined();
  expect(screen.getByText("10 pts")).toBeDefined();
  expect(screen.queryByRole("button", { name: "Submit" })).toBeNull();
});

it("hides the malus badge when the malus is zero", async () => {
  vi.mocked(getChallenge).mockResolvedValue(
    challengeDetail({ questions: [question({ points: 50, malus: 0 })] }),
  );
  renderChallenge();

  expect(await screen.findByText("50 pts")).toBeDefined();
  expect(screen.queryByText("0 pts")).toBeNull();
});

it("badges a question that carries trap flags", async () => {
  vi.mocked(getChallenge).mockResolvedValue(
    challengeDetail({ questions: [question({ has_trap: true })] }),
  );
  renderChallenge();

  expect(await screen.findByText("Traps")).toBeDefined();
  expect(screen.getByRole("button", { name: "Submit" })).toBeDefined();
});

it("replaces the form with a blocked marker once a trap is hit", async () => {
  vi.mocked(getChallenge).mockResolvedValue(
    challengeDetail({ questions: [question({ has_trap: true, is_blocked: true })] }),
  );
  renderChallenge();

  await userEvent.click(await screen.findByText("What is the flag?"));

  expect(screen.getByText(/This question is locked/)).toBeDefined();
  expect(screen.queryByRole("button", { name: "Submit" })).toBeNull();
  expect(screen.getByText("100 pts")).toBeDefined();
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
  renderChallenge();

  await clickAndCancel(await screen.findByRole("button", { name: "25 pts" }));
  expect(unlockHint).not.toHaveBeenCalled();

  await clickAndConfirm(screen.getByRole("button", { name: "25 pts" }), "Unlock");
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

const COMPLETED = { completed: true };
const FEEDBACK_ON = publicInfoWith({ enable_challenge_feedback: true });

it("hides the feedback card while the challenge is unfinished", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(FEEDBACK_ON);
  vi.mocked(getChallenge).mockResolvedValue(challengeDetail());
  renderChallenge();

  expect(await screen.findByRole("heading", { name: "Baby RSA" })).toBeDefined();
  expect(screen.queryByRole("button", { name: "Send feedback" })).toBeNull();
});

it("hides the feedback card when the feature is disabled", async () => {
  vi.mocked(getChallenge).mockResolvedValue(challengeDetail(COMPLETED));
  renderChallenge();

  expect(await screen.findByRole("heading", { name: "Baby RSA" })).toBeDefined();
  expect(screen.queryByRole("button", { name: "Send feedback" })).toBeNull();
});

it("sends a rating and comment once the challenge is completed", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(FEEDBACK_ON);
  vi.mocked(getChallenge).mockResolvedValue(challengeDetail(COMPLETED));
  vi.mocked(submitFeedback).mockResolvedValue({ rating: 4, comment: "Loved it" });
  renderChallenge();

  const submit = await screen.findByRole("button", { name: "Send feedback" });
  expect(submit).toHaveProperty("disabled", true);

  await userEvent.click(screen.getByRole("button", { name: "Rate 4 out of 5" }));
  await userEvent.type(
    screen.getByPlaceholderText("Anything you liked or would improve? (optional)"),
    "Loved it",
  );
  await userEvent.click(submit);

  await waitFor(() =>
    expect(submitFeedback).toHaveBeenCalledWith("c1", { rating: 4, comment: "Loved it" }),
  );
  expect(toast.success).toHaveBeenCalledWith("Thanks for the feedback!");
  // onSuccess patches the cache, so the card flips to edit mode without a refetch.
  expect(await screen.findByRole("button", { name: "Update feedback" })).toBeDefined();
  expect(getChallenge).toHaveBeenCalledTimes(1);
});

it("sends a null comment when the box is left empty", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(FEEDBACK_ON);
  vi.mocked(getChallenge).mockResolvedValue(challengeDetail(COMPLETED));
  vi.mocked(submitFeedback).mockResolvedValue({ rating: 5, comment: null });
  renderChallenge();

  await userEvent.click(await screen.findByRole("button", { name: "Rate 5 out of 5" }));
  await userEvent.click(screen.getByRole("button", { name: "Send feedback" }));

  await waitFor(() =>
    expect(submitFeedback).toHaveBeenCalledWith("c1", { rating: 5, comment: null }),
  );
});

it("prefills the card from the team's existing feedback", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(FEEDBACK_ON);
  vi.mocked(getChallenge).mockResolvedValue(
    challengeDetail({ ...COMPLETED, my_feedback: { rating: 2, comment: "Too guessy" } }),
  );
  renderChallenge();

  expect(await screen.findByRole("button", { name: "Update feedback" })).toBeDefined();
  expect(
    screen.getByPlaceholderText("Anything you liked or would improve? (optional)"),
  ).toHaveProperty("value", "Too guessy");
  expect(screen.getByRole("button", { name: "Rate 2 out of 5" })).toHaveProperty(
    "ariaPressed",
    "true",
  );
});

it("surfaces a failed feedback save", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(FEEDBACK_ON);
  vi.mocked(getChallenge).mockResolvedValue(challengeDetail(COMPLETED));
  vi.mocked(submitFeedback).mockRejectedValue(new Error("nope"));
  renderChallenge();

  await userEvent.click(await screen.findByRole("button", { name: "Rate 3 out of 5" }));
  await userEvent.click(screen.getByRole("button", { name: "Send feedback" }));

  await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Could not save your feedback"));
});

it("sends an anonymous visitor to the login page", async () => {
  const { router } = renderChallenge({ user: null });

  await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
  expect(getChallenge).not.toHaveBeenCalled();
});
