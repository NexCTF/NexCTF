import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { Markdown } from "./markdown";

it("embeds a YouTube link as a player", () => {
  const { container } = render(<Markdown>{"https://youtu.be/dQw4w9WgXcQ"}</Markdown>);
  expect(container.querySelector("iframe")?.getAttribute("src")).toBe(
    "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
  );
});

it("embeds a direct video file as a player", () => {
  const { container } = render(<Markdown>{"[clip](https://cdn.test/a.mp4?v=2)"}</Markdown>);
  expect(container.querySelector("video")?.getAttribute("src")).toBe("https://cdn.test/a.mp4?v=2");
});

it("leaves other links alone", () => {
  render(<Markdown>{"[docs](https://example.com/mp4-guide)"}</Markdown>);
  expect(screen.getByText("docs").getAttribute("href")).toBe("https://example.com/mp4-guide");
});

it("embeds an audio file as a player", () => {
  const { container } = render(<Markdown>{"[track](https://cdn.test/b.mp3)"}</Markdown>);
  expect(container.querySelector("audio")?.getAttribute("src")).toBe("https://cdn.test/b.mp3");
});

it("opens external links in a new tab but keeps internal ones in place", () => {
  render(<Markdown>{"[out](https://example.com) [in](/challenges)"}</Markdown>);
  expect(screen.getByText("out").getAttribute("target")).toBe("_blank");
  expect(screen.getByText("in").getAttribute("target")).toBe(null);
});

it("renders inline and block math", () => {
  const { container } = render(<Markdown>{"$c \\equiv m^e$\n\n$$n = pq$$"}</Markdown>);
  expect(container.querySelectorAll(".katex").length).toBe(2);
});

it("gives headings an id so they can be deep-linked", () => {
  const { container } = render(<Markdown>{"## Scoring rules"}</Markdown>);
  expect(container.querySelector("h2")?.id).toBe("scoring-rules");
});

it("embeds a stored file whose type is only known from the url fragment", () => {
  const { container } = render(
    <Markdown>{"[clip](/api/v1/file/2b1f/view#body%20cam.mp4)"}</Markdown>,
  );
  expect(container.querySelector("video")?.getAttribute("src")).toBe(
    "/api/v1/file/2b1f/view#body%20cam.mp4",
  );
});
