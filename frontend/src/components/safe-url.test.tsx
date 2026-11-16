import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { isHttpUrl, PlayerLink, SafeUrl, urlHostname } from "@/components/safe-url";

const SCRIPT_URL = ["javascript", "alert(1)"].join(":");

describe("isHttpUrl", () => {
  it.each(["https://example.com", "HTTP://example.com/a"])("accepts %s", (href) => {
    expect(isHttpUrl(href)).toBe(true);
  });

  it.each(["javascript:alert(1)", " javascript:alert(1)", "data:text/html,x", "//example.com", ""])(
    "refuses %s",
    (href) => {
      expect(isHttpUrl(href)).toBe(false);
    },
  );
});

describe("urlHostname", () => {
  it("returns the host the browser would open", () => {
    expect(urlHostname("https://good.example@evil.example/login")).toBe("evil.example");
  });

  it("returns null for anything but http(s)", () => {
    expect(urlHostname(SCRIPT_URL)).toBeNull();
    expect(urlHostname("https://")).toBeNull();
  });
});

describe("SafeUrl", () => {
  it("links an http(s) URL", () => {
    render(<SafeUrl href="https://example.com">site</SafeUrl>);
    const link = screen.getByRole("link", { name: "site" });
    expect(link.getAttribute("href")).toBe("https://example.com");
  });

  it("renders a script URL as plain text", () => {
    render(<SafeUrl href={SCRIPT_URL}>{SCRIPT_URL}</SafeUrl>);
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText(SCRIPT_URL)).toBeTruthy();
  });
});

describe("PlayerLink", () => {
  it("shows the real host next to a label", () => {
    render(<PlayerLink link={{ label: "github.com/me", url: "https://evil.example/x" }} />);
    const link = screen.getByRole("link");
    expect(link.getAttribute("href")).toBe("https://evil.example/x");
    expect(link.textContent).toBe("github.com/me(evil.example)");
  });

  it("shows the URL alone when there is no label", () => {
    render(<PlayerLink link={{ label: "", url: "https://example.com/me" }} />);
    expect(screen.getByRole("link").textContent).toBe("https://example.com/me");
  });

  it("does not link a script URL", () => {
    render(<PlayerLink link={{ label: "blog", url: SCRIPT_URL }} />);
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText(`blog (${SCRIPT_URL})`)).toBeTruthy();
  });
});
