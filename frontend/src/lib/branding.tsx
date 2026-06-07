import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useContext, useEffect } from "react";
import { type BrandingInfo, getPublicInfo } from "@/lib/api";

interface BrandingContext {
  name: string;
  logoUrl: string;
  faviconUrl: string;
  primaryColor: string;
}

const DEFAULT: BrandingContext = {
  name: "NexCTF",
  logoUrl: "",
  faviconUrl: "",
  primaryColor: "",
};

const Ctx = createContext<BrandingContext>(DEFAULT);

function hexLuminance(hex: string): number {
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;
  return 0.299 * r + 0.587 * g + 0.114 * b;
}

function applyPrimaryColor(hex: string) {
  const root = document.documentElement;
  root.style.setProperty("--primary", hex);
  root.style.setProperty(
    "--primary-foreground",
    hexLuminance(hex) > 0.5 ? "oklch(0.145 0 0)" : "oklch(0.985 0 0)",
  );
  root.style.setProperty("--ring", hex);
}

function clearPrimaryColor() {
  const root = document.documentElement;
  root.style.removeProperty("--primary");
  root.style.removeProperty("--primary-foreground");
  root.style.removeProperty("--ring");
}

function applyFavicon(url: string) {
  let link = document.querySelector<HTMLLinkElement>("link[rel~='icon']");
  if (!link) {
    link = document.createElement("link");
    link.rel = "icon";
    document.head.appendChild(link);
  }
  link.href = url || "/favicon.svg";
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

  const { data } = useQuery({
    queryKey: ["info", "public"],
    queryFn: getPublicInfo,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const branding: BrandingInfo = data?.branding ?? {
    name: DEFAULT.name,
    logo_url: "",
    favicon_url: "",
    primary_color: "",
  };

  const name = branding.name || DEFAULT.name;
  const logoUrl = branding.logo_url || "";
  const faviconUrl = branding.favicon_url || "";
  const primaryColor = branding.primary_color || "";

  // Invalidate public info when config changes via SSE
  usePublicConfigSSE(() => {
    void qc.invalidateQueries({ queryKey: ["info", "public"] });
  });

  useEffect(() => {
    document.title = name;
  }, [name]);

  useEffect(() => {
    if (primaryColor && /^#[0-9a-fA-F]{6}$/.test(primaryColor)) {
      applyPrimaryColor(primaryColor);
    } else {
      clearPrimaryColor();
    }
  }, [primaryColor]);

  useEffect(() => {
    applyFavicon(faviconUrl);
  }, [faviconUrl]);

  return (
    <Ctx.Provider value={{ name, logoUrl, faviconUrl, primaryColor }}>{children}</Ctx.Provider>
  );
}

export function useBranding(): BrandingContext {
  return useContext(Ctx);
}
