import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useContext, useEffect } from "react";
import { type BrandingInfo, getPublicInfo } from "@/lib/api";
import { deriveAccent, ensureContrast } from "@/lib/color";
import { parseTheme, useTheme } from "@/lib/theme";

interface BrandingContext {
  name: string;
  logoUrl: string;
  faviconUrl: string;
  loginBackgroundUrl: string;
}

export const DEFAULT_BRANDING: BrandingInfo = {
  name: "NexCTF",
  logo_url: "",
  favicon_url: "",
  accent_color: "",
  logo_url_dark: "",
  login_background_url: "",
  default_theme: "system",
  custom_css: "",
};

const DEFAULT: BrandingContext = {
  name: "NexCTF",
  logoUrl: "",
  faviconUrl: "",
  loginBackgroundUrl: "",
};

const Ctx = createContext<BrandingContext>(DEFAULT);

/** Surfaces the accent has to stay readable against, per theme. */
const LIGHT_SURFACE = "#FFFFFF";
const DARK_SURFACE = "#0B1210";
/** Text placed on an accent fill: the brand ink, or the brand light text. */
const INKS = { dark: "#04122B", light: "#EDEFED" };
const TEXT_CONTRAST = 4.5;
const UI_CONTRAST = 3;

/** The `--brand-*` overrides the theme reads through, keyed exactly as `index.css` spells them. */
function accentVars(hex: string): Record<string, string> {
  const light = deriveAccent(hex, LIGHT_SURFACE, INKS, TEXT_CONTRAST);
  const dark = deriveAccent(hex, DARK_SURFACE, INKS, TEXT_CONTRAST);
  return {
    "--brand-accent-light": light.color,
    "--brand-accent-dark": dark.color,
    "--brand-accent-on-light": light.on,
    "--brand-accent-on-dark": dark.on,
    "--brand-ring-light": ensureContrast(hex, LIGHT_SURFACE, UI_CONTRAST),
    "--brand-ring-dark": ensureContrast(hex, DARK_SURFACE, UI_CONTRAST),
  };
}

export const ACCENT_VARS = Object.keys(accentVars("#000000"));

function applyAccentColor(hex: string) {
  const root = document.documentElement;
  for (const [name, value] of Object.entries(accentVars(hex))) {
    root.style.setProperty(name, value);
  }
}

function clearAccentColor() {
  const root = document.documentElement;
  for (const name of ACCENT_VARS) root.style.removeProperty(name);
}

const CUSTOM_CSS_ID = "nexctf-custom-css";

function applyCustomCss(css: string) {
  let el = document.getElementById(CUSTOM_CSS_ID);
  if (!css) {
    el?.remove();
    return;
  }
  if (!el) {
    el = document.createElement("style");
    el.id = CUSTOM_CSS_ID;
    document.head.appendChild(el);
  }
  el.textContent = css;
}

const ICON_SELECTOR = "link[rel~='icon'], link[rel~='apple-touch-icon']";

function applyFavicon(url: string) {
  const links = Array.from(document.querySelectorAll<HTMLLinkElement>(ICON_SELECTOR));
  if (!links.length) {
    const link = document.createElement("link");
    link.rel = "icon";
    link.href = url || "/favicon.svg";
    document.head.appendChild(link);
    return;
  }
  for (const link of links) {
    link.dataset.defaultHref ??= link.getAttribute("href") ?? "";
    link.dataset.defaultType ??= link.getAttribute("type") ?? "";
    link.href = url || link.dataset.defaultHref;
    const type = url ? "" : link.dataset.defaultType;
    if (type) link.setAttribute("type", type);
    else link.removeAttribute("type");
  }
}

/** Open a persistent public SSE connection and call `onConfigUpdate` on each event. */
function usePublicConfigSSE(onConfigUpdate: () => void) {
  // biome-ignore lint/correctness/useExhaustiveDependencies: onConfigUpdate is stable (useCallback from parent)
  useEffect(() => {
    let es: EventSource | null = null;
    let closed = false;

    function connect() {
      if (closed) return;
      es = new EventSource("/api/v1/stream/public");
      es.addEventListener("config_update", () => onConfigUpdate());
      es.onerror = () => {
        es?.close();
        if (!closed) setTimeout(connect, 5000);
      };
    }

    connect();
    return () => {
      closed = true;
      es?.close();
    };
  }, []);
}

export function BrandingProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const { resolvedTheme, applyDefaultTheme } = useTheme();

  const { data } = useQuery({
    queryKey: ["info", "public"],
    queryFn: getPublicInfo,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const branding: BrandingInfo = data?.branding ?? DEFAULT_BRANDING;

  const name = branding.name || DEFAULT.name;
  const lightLogo = branding.logo_url || "";
  const darkLogo = branding.logo_url_dark || "";
  const logoUrl = (resolvedTheme === "dark" && darkLogo) || lightLogo;
  const faviconUrl = branding.favicon_url || "";
  const accentColor = branding.accent_color || "";
  const loginBackgroundUrl = branding.login_background_url || "";
  const customCss = branding.custom_css || "";
  const defaultTheme = branding.default_theme || "system";

  // Invalidate public info when config changes via SSE
  usePublicConfigSSE(() => {
    void qc.invalidateQueries({ queryKey: ["info", "public"] });
  });

  useEffect(() => {
    document.title = name;
  }, [name]);

  useEffect(() => {
    if (accentColor && /^#[0-9a-fA-F]{6}$/.test(accentColor)) {
      applyAccentColor(accentColor);
    } else {
      clearAccentColor();
    }
  }, [accentColor]);

  useEffect(() => {
    applyCustomCss(customCss);
  }, [customCss]);

  useEffect(() => {
    const theme = parseTheme(defaultTheme);
    if (theme) applyDefaultTheme(theme);
  }, [defaultTheme, applyDefaultTheme]);

  useEffect(() => {
    applyFavicon(faviconUrl);
  }, [faviconUrl]);

  return (
    <Ctx.Provider value={{ name, logoUrl, faviconUrl, loginBackgroundUrl }}>
      {children}
    </Ctx.Provider>
  );
}

export function useBranding(): BrandingContext {
  return useContext(Ctx);
}
