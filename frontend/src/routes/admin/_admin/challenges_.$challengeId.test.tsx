import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { expect, it } from "vitest";
import { QuestionFormFields } from "./challenges_.$challengeId";

function Harness() {
  const [form, setForm] = useState<Record<string, unknown>>({ trap_flags: [] });
  return (
    <QuestionFormFields form={form} onUpdate={(patch) => setForm((f) => ({ ...f, ...patch }))} />
  );
}

it("keeps newlines and spaces typed into the trap flags field", async () => {
  render(<Harness />);

  const field = screen.getByPlaceholderText("One flag per line");
  await userEvent.type(field, "nope one{enter}nope two");

  expect(field).toHaveProperty("value", "nope one\nnope two");
});
