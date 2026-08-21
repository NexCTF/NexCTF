import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { ChallengeLink, TargetCell } from "./table-cells";

// A relation the API names but cannot link (missing id) must still show the name.

it("shows the name when the relation has no id", () => {
  render(<ChallengeLink id={null} name="Pwn me" />);
  expect(screen.getByText("Pwn me")).toBeTruthy();
});

it("falls back to a dash when neither id nor name is known", () => {
  render(<ChallengeLink id={null} name={null} />);
  expect(screen.getByText("—")).toBeTruthy();
});

it("renders an unlinkable event target as plain text", () => {
  render(<TargetCell type="questions" id="q-1" label="Question 1" />);
  expect(screen.getByText("Question 1")).toBeTruthy();
  expect(screen.getByText("(questions)")).toBeTruthy();
});
