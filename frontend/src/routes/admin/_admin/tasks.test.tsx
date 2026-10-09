import { fireEvent, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { renderRoute } from "@/test/render";
import { Route } from "./tasks";

function render() {
  return renderRoute(Route, { path: "/admin/tasks" });
}

it("frames the backend's task dashboard", async () => {
  render();
  const frame = await screen.findByTitle("Task queue");
  expect(frame.getAttribute("src")).toBe("/api/admin/tasks/");
  const link = screen.getByRole("link", { name: /open in new tab/i });
  expect(link.getAttribute("href")).toBe("/api/admin/tasks/");
});

it("stores the admin's theme where the dashboard reads it", async () => {
  localStorage.setItem("nexctf-theme", "dark");
  render();
  await screen.findByTitle("Task queue");
  expect(localStorage.getItem("pgq-theme")).toBe("dark");
  localStorage.removeItem("nexctf-theme");
  localStorage.removeItem("pgq-theme");
});

it("reloads only the framed page, keeping where the admin navigated", async () => {
  render();
  const frame = await screen.findByTitle("Task queue");
  const reload = vi.fn();
  Object.defineProperty(frame, "contentWindow", { value: { location: { reload } } });
  fireEvent.click(screen.getByRole("button", { name: /refresh/i }));
  expect(reload).toHaveBeenCalledOnce();
});

it("opens the dashboard on the job the scheduler linked to", async () => {
  renderRoute(Route, { path: "/admin/tasks?job=42" });
  const frame = await screen.findByTitle("Task queue");
  expect(frame.getAttribute("src")).toBe("/api/admin/tasks/jobs/42");
  const link = screen.getByRole("link", { name: /open in new tab/i });
  expect(link.getAttribute("href")).toBe("/api/admin/tasks/jobs/42");
});
