import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import { searchAdminTeamsCursor, type Team } from "@/lib/api";
import { cursorPaginated } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";
import { TeamMultiSelect } from "./team-multi-select";
import { TeamSingleSelect } from "./team-single-select";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  searchAdminTeamsCursor: vi.fn(),
}));

const teams = [
  { id: "t-1", name: "Alpha" },
  { id: "t-2", name: "Bravo" },
] as Team[];

beforeEach(() => {
  vi.mocked(searchAdminTeamsCursor).mockImplementation(async (search) =>
    cursorPaginated(teams.filter((team) => team.name.startsWith(search))),
  );
});

function MultiHarness({ onChange }: { onChange: (ids: string[]) => void }) {
  const [value, setValue] = useState<string[]>([]);
  return (
    <TeamMultiSelect
      value={value}
      onChange={(ids) => {
        setValue(ids);
        onChange(ids);
      }}
    />
  );
}

it("picks teams from the keyboard and keeps the popup open", async () => {
  const onChange = vi.fn();
  renderWithQuery(<MultiHarness onChange={onChange} />);

  await userEvent.click(screen.getByRole("combobox"));
  expect(await screen.findByRole("option", { name: "Alpha" })).toBeTruthy();

  await userEvent.keyboard("{ArrowDown}{Enter}");
  expect(onChange).toHaveBeenLastCalledWith(["t-1"]);

  const search = screen.getByPlaceholderText("Search…");
  await userEvent.type(search, "Br");
  await waitFor(() => expect(screen.getAllByRole("option")).toHaveLength(1));
  await userEvent.keyboard("{ArrowDown}{Enter}");
  expect(onChange).toHaveBeenLastCalledWith(["t-1", "t-2"]);
  expect(search).toHaveProperty("value", "Br");
  expect(screen.getByRole("listbox")).toBeTruthy();

  await userEvent.click(screen.getByRole("button", { name: "Remove Alpha" }));
  expect(onChange).toHaveBeenLastCalledWith(["t-2"]);
});

it("selects and clears a single team", async () => {
  const onChange = vi.fn();
  const { rerender } = renderWithQuery(<TeamSingleSelect value={null} onChange={onChange} />);

  await userEvent.click(screen.getByRole("combobox"));
  await userEvent.click(await screen.findByRole("option", { name: "Bravo" }));
  expect(onChange).toHaveBeenLastCalledWith("t-2");

  rerender(<TeamSingleSelect value="t-2" onChange={onChange} />);
  expect(screen.getByRole("combobox").textContent).toContain("Bravo");

  await userEvent.click(screen.getByRole("button", { name: "Clear team" }));
  expect(onChange).toHaveBeenLastCalledWith(null);
});
