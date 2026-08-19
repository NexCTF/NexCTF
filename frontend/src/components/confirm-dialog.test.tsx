import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { DeleteButton } from "./confirm-dialog";

function renderInRow(onConfirm: () => void, onRowClick: () => void) {
  return render(
    <table>
      <tbody>
        <tr onClick={onRowClick}>
          <td>
            <DeleteButton description="Delete this row?" onConfirm={onConfirm} />
          </td>
        </tr>
      </tbody>
    </table>,
  );
}

it("opens the dialog without triggering the row click", async () => {
  const onConfirm = vi.fn();
  const onRowClick = vi.fn();
  renderInRow(onConfirm, onRowClick);

  await userEvent.click(screen.getByRole("button", { name: "Delete" }));

  expect(screen.getByRole("dialog")).toBeTruthy();
  expect(screen.getByText("Delete this row?")).toBeTruthy();
  expect(onRowClick).not.toHaveBeenCalled();
  expect(onConfirm).not.toHaveBeenCalled();
});

it("confirms only once the dialog is accepted", async () => {
  const onConfirm = vi.fn();
  renderInRow(onConfirm, vi.fn());

  await userEvent.click(screen.getByRole("button", { name: "Delete" }));
  const dialog = screen.getByRole("dialog");
  await userEvent.click(within(dialog).getByRole("button", { name: "Delete" }));

  expect(onConfirm).toHaveBeenCalledTimes(1);
});

it("cancels without confirming", async () => {
  const onConfirm = vi.fn();
  renderInRow(onConfirm, vi.fn());

  await userEvent.click(screen.getByRole("button", { name: "Delete" }));
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

  expect(onConfirm).not.toHaveBeenCalled();
});

it("confirms from inside an already-open dialog", async () => {
  const onConfirm = vi.fn();
  render(
    <Dialog open>
      <DialogContent>
        <DialogTitle>Answer</DialogTitle>
        <DeleteButton description="Delete this submission?" onConfirm={onConfirm} />
      </DialogContent>
    </Dialog>,
  );

  await userEvent.click(screen.getByRole("button", { name: "Delete" }));
  const confirm = screen.getByText("Delete this submission?").closest("[role=dialog]");
  await userEvent.click(within(confirm as HTMLElement).getByRole("button", { name: "Delete" }));

  expect(onConfirm).toHaveBeenCalledTimes(1);
  expect(screen.getByText("Answer")).toBeTruthy();
});
