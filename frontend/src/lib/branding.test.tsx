import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { getPublicInfo } from "@/lib/api";
import { ACCENT_VARS, BrandingProvider, DEFAULT_BRANDING } from "@/lib/branding";
import { ThemeProvider } from "@/lib/theme";
import { publicInfo } from "@/test/fixtures";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getPublicInfo: vi.fn(),
}));

function renderBranding() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <BrandingProvider>
          <div />
        </BrandingProvider>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

function brandingInfo(overrides: Partial<typeof DEFAULT_BRANDING>) {
  return publicInfo({ branding: { ...DEFAULT_BRANDING, ...overrides } });
}

function readVar(name: string) {
  return document.documentElement.style.getPropertyValue(name);
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  document.documentElement.style.cssText = "";
  document.getElementById("nexctf-custom-css")?.remove();
});

it("derives a per-theme accent that stays readable on both surfaces", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(brandingInfo({ accent_color: "#3b82f6" }));
  renderBranding();

  // Too light for white, so light mode gets a darkened shade; dark mode keeps the raw accent.
  await waitFor(() => expect(readVar("--brand-accent-dark")).toBe("#3b82f6"));
  expect(readVar("--brand-accent-light")).not.toBe("#3b82f6");
  expect(readVar("--brand-accent-on-dark")).toBe("#04122B");
});

it("clears every accent variable when the color is unset", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(brandingInfo({ accent_color: "#3b82f6" }));
  const { unmount } = renderBranding();
  await waitFor(() => expect(readVar("--brand-accent-light")).not.toBe(""));
  unmount();

  vi.mocked(getPublicInfo).mockResolvedValue(brandingInfo({ accent_color: "" }));
  renderBranding();

  await waitFor(() => {
    for (const name of ACCENT_VARS) expect(readVar(name)).toBe("");
  });
});

it("injects custom CSS as text and removes it when emptied", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(brandingInfo({ custom_css: "body{opacity:.5}" }));
  const { unmount } = renderBranding();

  await waitFor(() =>
    expect(document.getElementById("nexctf-custom-css")?.textContent).toBe("body{opacity:.5}"),
  );
  unmount();

  vi.mocked(getPublicInfo).mockResolvedValue(brandingInfo({ custom_css: "" }));
  renderBranding();
  await waitFor(() => expect(document.getElementById("nexctf-custom-css")).toBeNull());
});

it("seeds the configured default theme only while the visitor has no stored choice", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(brandingInfo({ default_theme: "dark" }));
  const { unmount } = renderBranding();
  await waitFor(() => expect(document.documentElement.classList.contains("dark")).toBe(true));
  unmount();

  localStorage.setItem("nexctf-theme", "light");
  renderBranding();
  await waitFor(() => expect(document.documentElement.classList.contains("dark")).toBe(false));
});
