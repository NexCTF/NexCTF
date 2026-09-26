import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import {
  adminBundleExportUrl,
  applyAdminBundleImport,
  type BundlePlan,
  type BundlePlanEntry,
  planAdminBundleImport,
} from "@/lib/api";
import { renderRoute } from "@/test/render";
import { Route } from "./bundle";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  planAdminBundleImport: vi.fn(),
  applyAdminBundleImport: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));

function entry(overrides: Partial<BundlePlanEntry>): BundlePlanEntry {
  return {
    kind: "challenge",
    id: "c-1",
    label: "Baby Web",
    action: "update",
    parent_id: null,
    changes: {},
    reason: null,
    ...overrides,
  };
}

function plan(entries: BundlePlanEntry[]): BundlePlan {
  const counts: Record<string, number> = {};
  for (const e of entries) counts[e.action] = (counts[e.action] ?? 0) + 1;
  return {
    import_key: "imports/11111111-1111-1111-1111-111111111111.zip",
    prune: false,
    manifest: {
      format_version: 1,
      nexctf_version: "0.11.0",
      exported_at: "2026-09-19T12:00:00Z",
      challenge_types: ["standard"],
      solve_types: ["match"],
      plugins: [],
    },
    counts,
    entries,
  };
}

async function uploadArchive() {
  await screen.findByRole("button", { name: /Choose an archive/ });
  const file = new File([new Uint8Array([0x50, 0x4b])], "bundle.zip", {
    type: "application/zip",
  });
  const input = document.querySelector<HTMLInputElement>('input[type="file"]');
  if (!input) throw new Error("no file input");
  await userEvent.upload(input, file);
}

beforeEach(() => {
  vi.mocked(applyAdminBundleImport).mockResolvedValue({ counts: { update: 1 }, entries: [] });
});

it("the export button downloads the archive directly", async () => {
  renderRoute(Route, { path: "/admin/bundle" });

  const link = await screen.findByRole("link", { name: /Export/ });

  expect(link.getAttribute("href")).toBe(
    adminBundleExportUrl({ includeFiles: true, includeSecrets: false }),
  );
  expect(link.hasAttribute("download")).toBe(true);
});

it("leaving files out is carried into the export URL", async () => {
  renderRoute(Route, { path: "/admin/bundle" });

  await userEvent.click(
    await screen.findByRole("switch", { name: "Include uploaded file attachments" }),
  );

  expect(screen.getByRole("link", { name: /Export/ }).getAttribute("href")).toBe(
    adminBundleExportUrl({ includeFiles: false, includeSecrets: false }),
  );
});

it("secrets are off until asked for, and warn once on", async () => {
  renderRoute(Route, { path: "/admin/bundle" });

  const toggle = await screen.findByRole("switch", { name: "Include secret settings" });
  expect(toggle.getAttribute("aria-checked")).toBe("false");
  expect(screen.queryByText(/clear text/)).toBeNull();

  await userEvent.click(toggle);

  expect(screen.getByText(/clear text/)).toBeTruthy();
  expect(screen.getByRole("link", { name: /Export/ }).getAttribute("href")).toBe(
    adminBundleExportUrl({ includeFiles: true, includeSecrets: true }),
  );
});

it("the plan opens as a modal over the three panels, not in place of them", async () => {
  vi.mocked(planAdminBundleImport).mockResolvedValue(plan([entry({})]));
  renderRoute(Route, { path: "/admin/bundle" });

  await uploadArchive();

  const dialog = await screen.findByRole("dialog");
  expect(within(dialog).getByText("Review the import")).toBeTruthy();
  // Still mounted behind the modal, which correctly makes them inert meanwhile.
  expect(screen.getByRole("link", { name: /Export/, hidden: true })).toBeTruthy();
  expect(screen.getByText("Git remote")).toBeTruthy();

  await userEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));

  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(screen.getByRole("link", { name: /Export/ })).toBeTruthy();
});

it("cancelling the modal writes nothing and drops the plan", async () => {
  vi.mocked(planAdminBundleImport).mockResolvedValue(plan([entry({})]));
  renderRoute(Route, { path: "/admin/bundle" });
  await uploadArchive();
  const dialog = await screen.findByRole("dialog");

  await userEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));

  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(applyAdminBundleImport).not.toHaveBeenCalled();
});

it("a second upload reviews the new plan, not the old one", async () => {
  vi.mocked(planAdminBundleImport).mockResolvedValue(plan([entry({ id: "c-1", label: "First" })]));
  renderRoute(Route, { path: "/admin/bundle" });
  await uploadArchive();
  await screen.findByRole("dialog");
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

  vi.mocked(planAdminBundleImport).mockResolvedValue(plan([entry({ id: "c-2", label: "Second" })]));
  await uploadArchive();

  const dialog = await screen.findByRole("dialog");
  expect(within(dialog).getByText("Second")).toBeTruthy();
  expect(within(dialog).queryByText("First")).toBeNull();
});

it("the git remote panel is present but not usable yet", async () => {
  renderRoute(Route, { path: "/admin/bundle" });

  expect(await screen.findByText("Git remote")).toBeTruthy();
  expect(screen.getByText("Not available yet.")).toBeTruthy();
});

it("uploading shows the plan and writes nothing on its own", async () => {
  vi.mocked(planAdminBundleImport).mockResolvedValue(
    plan([entry({ changes: { title: ["Baby Web", "Renamed"] } })]),
  );
  renderRoute(Route, { path: "/admin/bundle" });

  await uploadArchive();

  expect(await screen.findByText("Review the import")).toBeTruthy();
  expect(applyAdminBundleImport).not.toHaveBeenCalled();
});

it("applies the complete reviewed plan", async () => {
  vi.mocked(planAdminBundleImport).mockResolvedValue(
    plan([
      entry({ id: "c-1", label: "Kept" }),
      entry({ id: "c-2", label: "Dropped", kind: "page" }),
    ]),
  );
  renderRoute(Route, { path: "/admin/bundle" });
  await uploadArchive();
  await screen.findByText("Review the import");

  await userEvent.click(screen.getByRole("button", { name: /Apply 2 change/ }));

  expect(applyAdminBundleImport).toHaveBeenCalledWith(
    "imports/11111111-1111-1111-1111-111111111111.zip",
    false,
  );
});

it("a skipped entry is shown but does not count as a change to apply", async () => {
  vi.mocked(planAdminBundleImport).mockResolvedValue(
    plan([
      entry({ id: "c-1", label: "Real edit" }),
      entry({
        id: "ctf.unknown",
        kind: "config",
        label: "ctf.unknown",
        action: "skipped",
        reason: "this instance has no such setting",
      }),
    ]),
  );
  renderRoute(Route, { path: "/admin/bundle" });
  await uploadArchive();
  const dialog = await screen.findByRole("dialog");

  expect(within(dialog).getByText("ctf.unknown")).toBeTruthy();
  expect(within(dialog).getByRole("button", { name: /Apply 1 change/ })).toBeTruthy();
});

it("a refused entry prevents applying the plan", async () => {
  vi.mocked(planAdminBundleImport).mockResolvedValue(
    plan([entry({ action: "conflict", label: "Clashing", reason: "title is taken" })]),
  );
  renderRoute(Route, { path: "/admin/bundle" });
  await uploadArchive();
  await screen.findByText("Review the import");

  expect(
    (screen.getByRole("button", { name: /Apply 0 change/ }) as HTMLButtonElement).disabled,
  ).toBe(true);
  expect(screen.getByText("title is taken")).toBeTruthy();
});
