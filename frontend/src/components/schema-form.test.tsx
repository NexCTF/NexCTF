import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import type { JsonSchema } from "@/lib/api";
import { SchemaFields } from "./schema-form";

const requiredSchema: JsonSchema = {
  properties: { until: { title: "Until", type: "string", format: "date-time" } },
  required: ["until"],
};

const nullableSchema: JsonSchema = {
  properties: {
    until: {
      title: "Until",
      anyOf: [{ type: "string", format: "date-time" }, { type: "null" }],
      default: null,
    },
  },
};

const dateSchema: JsonSchema = {
  properties: {
    day: { title: "Day", anyOf: [{ type: "string", format: "date" }, { type: "null" }] },
  },
};

function renderFields(schema: JsonSchema, values: Record<string, unknown>) {
  const onChange = vi.fn();
  render(<SchemaFields schema={schema} values={values} onChange={onChange} />);
  return onChange;
}

it("renders a date-time property as a picker that sends UTC ISO", () => {
  const onChange = renderFields(requiredSchema, { until: "" });
  const input = screen.getByLabelText(/Until/);

  expect(input).toHaveProperty("type", "datetime-local");
  fireEvent.change(input, { target: { value: "2030-01-01T12:00" } });

  expect(onChange).toHaveBeenCalledWith("until", new Date("2030-01-01T12:00").toISOString());
  expect(onChange.mock.lastCall?.[1]).toMatch(/Z$/);
});

it("shows a stored UTC value in local time", () => {
  renderFields(nullableSchema, { until: "2030-01-01T12:00:00Z" });
  const local = new Date("2030-01-01T12:00:00Z");
  const pad = (n: number) => String(n).padStart(2, "0");

  expect(screen.getByLabelText("Until")).toHaveProperty(
    "value",
    `${local.getFullYear()}-${pad(local.getMonth() + 1)}-${pad(local.getDate())}T${pad(local.getHours())}:${pad(local.getMinutes())}`,
  );
});

it("clears a nullable date-time back to null", async () => {
  const onChange = renderFields(nullableSchema, { until: "2030-01-01T12:00:00Z" });

  await userEvent.click(screen.getByRole("button", { name: "Clear" }));

  expect(onChange).toHaveBeenCalledWith("until", null);
});

it("sends null when a nullable date-time input is emptied", () => {
  const onChange = renderFields(nullableSchema, { until: "2030-01-01T12:00:00Z" });

  fireEvent.change(screen.getByLabelText("Until"), { target: { value: "" } });

  expect(onChange).toHaveBeenCalledWith("until", null);
});

it("offers no clear button on a required date-time", () => {
  renderFields(requiredSchema, { until: "2030-01-01T12:00:00Z" });

  expect(screen.queryByRole("button", { name: "Clear" })).toBeNull();
});

it("renders a date property as a date input without timezone shift", async () => {
  const onChange = renderFields(dateSchema, { day: "2030-01-01" });
  const input = screen.getByLabelText("Day");

  expect(input).toHaveProperty("type", "date");
  fireEvent.change(input, { target: { value: "2030-02-03" } });
  expect(onChange).toHaveBeenCalledWith("day", "2030-02-03");

  await userEvent.click(screen.getByRole("button", { name: "Clear" }));
  expect(onChange).toHaveBeenCalledWith("day", null);
});
