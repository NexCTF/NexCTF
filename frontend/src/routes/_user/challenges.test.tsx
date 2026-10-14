import { screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError, getChallenges, getPublicInfo } from "@/lib/api";
import type { AuthContext } from "@/lib/auth";
import { challenge, publicInfo, publicInfoWith, user } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { Route } from "./challenges";

const renderChallenges = (auth: Partial<AuthContext> = { user: user() }) =>
  renderRoute(Route, { path: "/challenges", auth });

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getPublicInfo: vi.fn(),
  getChallenges: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfo());
  vi.mocked(getChallenges).mockResolvedValue([]);
});

it("groups the challenges by category and links to each one", async () => {
  vi.mocked(getChallenges).mockResolvedValue([
    challenge({ id: "c1", title: "Baby RSA", category: "crypto" }),
    challenge({ id: "c2", title: "Stack Smash", category: "pwn" }),
    challenge({ id: "c3", title: "Mystery", category: null }),
  ]);
  renderChallenges();

  await screen.findByRole("heading", { name: "crypto" });
  expect(screen.getByRole("heading", { name: "pwn" })).toBeDefined();
  expect(screen.getByRole("heading", { name: "Uncategorized" })).toBeDefined();

  const link = screen.getByText("Baby RSA").closest("a");
  expect(link?.getAttribute("href")).toBe("/challenges/c1");
});

it("shows solve progress per challenge", async () => {
  vi.mocked(getChallenges).mockResolvedValue([
    challenge({ question_count: 4, solved_count: 1 }),
    challenge({ id: "c2", title: "Solo", question_count: 1, solved_count: 0 }),
  ]);
  renderChallenges();

  expect(await screen.findByText("1/4 questions")).toBeDefined();
  expect(screen.getByText("0/1 question")).toBeDefined();
});

it("shows an empty state when nothing is published", async () => {
  renderChallenges();

  expect(await screen.findByText("No challenges available yet.")).toBeDefined();
});

it("explains why challenges are unavailable before the start", async () => {
  vi.mocked(getChallenges).mockRejectedValue(
    new ApiError(403, "CTF not started", "The CTF has not started yet.", "CTF-403-NOT-STARTED"),
  );
  renderChallenges();

  expect(await screen.findByText("The CTF has not started yet.")).toBeDefined();
  expect(screen.queryByText("No challenges available yet.")).toBeNull();
});

it("warns once the event has ended", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfoWith({ end_time: "2020-01-01T00:00:00Z" }));
  renderChallenges();

  expect(
    await screen.findByText("The CTF has ended. Submissions are no longer accepted."),
  ).toBeDefined();
});

it("sends an anonymous visitor to the login page without fetching challenges", async () => {
  const { router } = renderChallenges({ user: null });

  await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
  expect(getChallenges).not.toHaveBeenCalled();
});

it("pluralises the question count and labels challenges without a category", async () => {
  vi.mocked(getChallenges).mockResolvedValue([
    challenge({ id: "c1", category: null, question_count: 1, solved_count: 0 }),
  ]);
  renderRoute(Route, { path: "/challenges", auth: { user: user() } });

  expect(await screen.findByText("0/1 question")).toBeDefined();
  expect(screen.getByText("Uncategorized")).toBeDefined();
});
