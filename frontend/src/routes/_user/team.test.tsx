import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { beforeEach, expect, it, vi } from "vitest";
import {
  ApiError,
  createTeam,
  getMyTeam,
  getPublicInfo,
  joinTeam,
  leaveTeam,
  rotateInviteCode,
} from "@/lib/api";
import type { AuthContext } from "@/lib/auth";
import { publicInfo, publicInfoWith, team, user } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { Route } from "./team";

const renderTeam = (auth: Partial<AuthContext> = { user: user() }) =>
  renderRoute(Route, { path: "/team", auth });

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getPublicInfo: vi.fn(),
  getMyTeam: vi.fn(),
  createTeam: vi.fn(),
  joinTeam: vi.fn(),
  leaveTeam: vi.fn(),
  rotateInviteCode: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));

beforeEach(() => {
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfo());
  vi.mocked(getMyTeam).mockResolvedValue(null);
});

it("creates a team", async () => {
  vi.mocked(createTeam).mockResolvedValue(team());
  renderTeam();

  await userEvent.type(await screen.findByLabelText("Team name"), "Alpha");
  await userEvent.click(screen.getByRole("button", { name: "Create team" }));

  await waitFor(() => expect(createTeam).toHaveBeenCalledWith("Alpha"));
});

it("joins a team with an invite code, normalised to upper case", async () => {
  vi.mocked(joinTeam).mockResolvedValue(team());
  renderTeam();

  await userEvent.type(await screen.findByLabelText("Invite code"), "  abc123  ");
  await userEvent.click(screen.getByRole("button", { name: "Join" }));

  await waitFor(() => expect(joinTeam).toHaveBeenCalledWith("ABC123"));
});

it("surfaces a join failure as a toast", async () => {
  vi.mocked(joinTeam).mockRejectedValue(new ApiError(404, "Not Found", "No such invite code"));
  renderTeam();

  await userEvent.type(await screen.findByLabelText("Invite code"), "nope");
  await userEvent.click(screen.getByRole("button", { name: "Join" }));

  await waitFor(() => expect(toast.error).toHaveBeenCalledWith("No such invite code"));
});

it("hides the create form when team creation is closed", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfoWith({ allow_team_creation: false }));
  renderTeam();

  expect(await screen.findByText("Team creation is currently disabled.")).toBeDefined();
  expect(screen.getByLabelText("Invite code")).toBeDefined();
});

it("hides both forms when team changes are frozen", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfoWith({ allow_team_changes: false }));
  renderTeam();

  expect(await screen.findByText("Team changes are currently disabled.")).toBeDefined();
  expect(screen.queryByLabelText("Invite code")).toBeNull();
  expect(screen.queryByLabelText("Team name")).toBeNull();
});

it("shows the team with its invite code and member count", async () => {
  vi.mocked(getMyTeam).mockResolvedValue(team({ member_count: 2 }));
  renderTeam();

  expect(await screen.findByRole("heading", { name: "Alpha" })).toBeDefined();
  expect(screen.getByText("2 / 4")).toBeDefined();
  expect(screen.getByText("INVITE123")).toBeDefined();
});

it("asks before leaving the team", async () => {
  vi.mocked(getMyTeam).mockResolvedValue(team());
  vi.mocked(leaveTeam).mockResolvedValue(undefined);
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
  renderTeam();

  await userEvent.click(await screen.findByRole("button", { name: "Leave team" }));
  expect(leaveTeam).not.toHaveBeenCalled();

  confirmSpy.mockReturnValue(true);
  await userEvent.click(screen.getByRole("button", { name: "Leave team" }));
  await waitFor(() => expect(leaveTeam).toHaveBeenCalled());
});

it("swaps in the new invite code after regenerating it", async () => {
  vi.mocked(getMyTeam).mockResolvedValue(team());
  vi.mocked(rotateInviteCode).mockResolvedValue("NEWCODE9");
  renderTeam();

  await userEvent.click(await screen.findByRole("button", { name: "Regenerate" }));

  expect(await screen.findByText("NEWCODE9")).toBeDefined();
});

it("hides the invite section and leave button when changes are frozen", async () => {
  vi.mocked(getMyTeam).mockResolvedValue(team());
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfoWith({ allow_team_changes: false }));
  renderTeam();

  expect(await screen.findByRole("heading", { name: "Alpha" })).toBeDefined();
  expect(screen.queryByText("INVITE123")).toBeNull();
  expect(screen.queryByRole("button", { name: "Leave team" })).toBeNull();
});

it("sends an anonymous visitor to the login page", async () => {
  const { router } = renderTeam({ user: null });

  await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
  expect(getMyTeam).not.toHaveBeenCalled();
});
