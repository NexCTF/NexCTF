import { QueryClient } from "@tanstack/react-query";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { beforeEach, expect, it, vi } from "vitest";
import {
  ApiError,
  getChallenge,
  getPublicInfo,
  submitAnswer,
  submitFeedback,
  unlockHint,
} from "@/lib/api";
import type { AuthContext } from "@/lib/auth";
import {
  challengeDetail,
  hint,
  publicInfo,
  publicInfoWith,
  question,
  team,
  user,
} from "@/test/fixtures";
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

function renderChallenge(auth: Partial<AuthContext> = { user: user() }, queryClient?: QueryClient) {
  return renderRoute(Route, {
    path: "/challenges/c1",
    routePath: "/challenges/$challengeId",
    auth,
    queryClient,
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
  });
  renderChallenge();

  await userEvent.type(await screen.findByPlaceholderText("Enter your answer…"), "flag_x");
  await userEvent.click(screen.getByRole("button", { name: "Submit" }));

  await waitFor(() => expect(submitAnswer).toHaveBeenCalledWith("c1", "q1", "flag_x"));
  expect(toast.success).toHaveBeenCalledWith("Correct! 🎉");
});

it("reports a wrong answer without clearing the field", async () => {
  vi.mocked(submitAnswer).mockResolvedValue({
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
  vi.mocked(unlockHint).mockResolvedValue(
    hint({ cost: 25, is_unlocked: true, content: "Look closer" }),
  );
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

it("explains a challenge that cannot be opened instead of a blank page", async () => {
  vi.mocked(getChallenge).mockRejectedValue(new ApiError(404, "Not Found", "Challenge not found"));
  renderChallenge();

  expect(await screen.findByText("Challenge not found")).toBeDefined();
  expect(screen.getByRole("link", { name: /Back to challenges/ })).toBeDefined();
  expect(getChallenge).toHaveBeenCalledTimes(1);
});

it("renders an unlocked hint as Markdown", async () => {
  vi.mocked(getChallenge).mockResolvedValue(
    challengeDetail({
      questions: [
        question({
          hints: [hint({ is_unlocked: true, content: "Try **base64**" })],
        }),
      ],
    }),
  );
  const { container } = renderChallenge();

  await screen.findByText("base64");
  expect(container.querySelector("strong")?.textContent).toBe("base64");
});

it("shows an unlocked hint without reloading the challenge", async () => {
  vi.mocked(getChallenge).mockResolvedValue(
    challengeDetail({
      questions: [
        question({
          hints: [hint()],
        }),
      ],
    }),
  );
  vi.mocked(unlockHint).mockResolvedValue(hint({ is_unlocked: true, content: "Look closer" }));
  renderChallenge();

  await userEvent.click(await screen.findByRole("button", { name: "Unlock" }));

  expect(await screen.findByText("Look closer")).toBeDefined();
  expect(getChallenge).toHaveBeenCalledTimes(1);
});

it("refreshes the team's progress after a correct solve", async () => {
  vi.mocked(submitAnswer).mockResolvedValue({
    is_correct: true,
    already_solved: false,
    points_earned: 100,
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(["my-team"], team());
  client.setQueryData(["team-score", "t1"], { total: 0 });
  renderChallenge({ user: user() }, client);

  await userEvent.type(await screen.findByPlaceholderText("Enter your answer…"), "flag_x");
  await userEvent.click(screen.getByRole("button", { name: "Submit" }));

  await waitFor(() => expect(client.getQueryState(["my-team"])?.isInvalidated).toBe(true));
  expect(client.getQueryState(["team-score", "t1"])?.isInvalidated).toBe(true);
});

it("locks answers and hint unlocks once the event has ended", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfoWith({ end_time: "2020-01-01T00:00:00Z" }));
  vi.mocked(getChallenge).mockResolvedValue(
    challengeDetail({ questions: [question({ hints: [hint()] })] }),
  );
  renderChallenge();

  await screen.findByText("The CTF has ended. Submissions are no longer accepted.");
  await userEvent.type(screen.getByPlaceholderText("Enter your answer…"), "flag_x");
  expect(screen.getByRole("button", { name: "Submit" })).toHaveProperty("disabled", true);
  expect(screen.getByRole("button", { name: "Unlock" })).toHaveProperty("disabled", true);
});

it("locks answers while challenges are previewable before the start", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(
    publicInfoWith({ start_time: "2099-01-01T00:00:00Z", freeze_time: "", end_time: "" }),
  );
  renderChallenge();

  await screen.findByText("The CTF has not started yet. Submissions open at the start.");
  await userEvent.type(screen.getByPlaceholderText("Enter your answer…"), "flag_x");
  expect(screen.getByRole("button", { name: "Submit" })).toHaveProperty("disabled", true);
});

it("locks answers when the end passes while the page is open", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  try {
    vi.mocked(getPublicInfo).mockResolvedValue(
      publicInfoWith({ freeze_time: "", end_time: new Date(Date.now() + 60_000).toISOString() }),
    );
    renderChallenge();

    const typist = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    await typist.type(await screen.findByPlaceholderText("Enter your answer…"), "flag_x");
    const submit = screen.getByRole("button", { name: "Submit" });
    expect(submit).toHaveProperty("disabled", false);

    await vi.advanceTimersByTimeAsync(60_000);
    expect(submit).toHaveProperty("disabled", true);
    expect(
      screen.getByText("The CTF has ended. Submissions are no longer accepted."),
    ).toBeDefined();
  } finally {
    vi.useRealTimers();
  }
});
