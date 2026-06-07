import { useEffect, useRef, useState } from "react";
import type { PublicInfo } from "@/lib/api";

type CapWidget = HTMLElement & {
  solve?: () => void;
  reset?: () => void;
};

declare module "react" {
  namespace JSX {
    interface IntrinsicElements {
      "cap-widget": React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement> & {
        "data-cap-api-endpoint"?: string;
        style?: React.CSSProperties;
      };
    }
  }
}

export function useCaptcha(publicInfo: PublicInfo | undefined) {
  const captchaEnabled = publicInfo?.captcha?.enabled ?? false;
  const captchaWidgetEndpoint = publicInfo?.captcha?.widget_endpoint ?? "";
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const capWidgetRef = useRef<CapWidget | null>(null);

  // Load the cap-widget script once
  useEffect(() => {
    if (!captchaEnabled) return;
    const src = "https://cdn.jsdelivr.net/npm/cap-widget";
    if (document.querySelector(`script[src="${src}"]`)) return;
    const script = document.createElement("script");
    script.src = src;
    script.type = "module";
    document.head.appendChild(script);
  }, [captchaEnabled]);

  // biome-ignore lint/correctness/useExhaustiveDependencies: captchaEnabled gates when cap-widget is in DOM
  useEffect(() => {
    const el = capWidgetRef.current;
    if (!el) return;

    const handler = (e: Event) => {
      const token = (e as CustomEvent<{ token: string }>).detail?.token;
      if (token) setCaptchaToken(token);
    };
    el.addEventListener("solve", handler);

    // Programmatic mode: trigger solving automatically once the widget is ready.
    // The widget exposes a solve() method; we call it after a short delay to let
    // the web component upgrade (customElements.define runs async).
    const timer = setTimeout(() => el.solve?.(), 300);

    return () => {
      el.removeEventListener("solve", handler);
      clearTimeout(timer);
    };
  }, [captchaEnabled]);

  function resetCaptcha() {
    setCaptchaToken(null);
    const el = capWidgetRef.current;
    el?.reset?.();
    // Re-trigger solving automatically after reset
    setTimeout(() => el?.solve?.(), 100);
  }

  const captchaSolved = !captchaEnabled || !!captchaToken;

  return {
    captchaEnabled,
    captchaWidgetEndpoint,
    captchaToken,
    capWidgetRef,
    resetCaptcha,
    captchaSolved,
  };
}
