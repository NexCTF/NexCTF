import { useEffect, useRef, useState } from "react";
import type { PublicInfo } from "@/lib/api";

type AltchaWidget = HTMLElement & {
  verify?: () => Promise<{ payload: string } | null>;
  reset?: () => void;
};

declare module "react" {
  namespace JSX {
    interface IntrinsicElements {
      "altcha-widget": React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement> & {
        challenge?: string;
        auto?: string;
        style?: React.CSSProperties;
      };
    }
  }
}

export function useCaptcha(publicInfo: PublicInfo | undefined) {
  const captchaEnabled = publicInfo?.captcha?.enabled ?? false;
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const widgetRef = useRef<AltchaWidget | null>(null);

  // Load the altcha widget script once
  useEffect(() => {
    if (!captchaEnabled) return;
    const src = "https://cdn.jsdelivr.net/npm/altcha@3.2.2/dist/main/altcha.min.js";
    if (document.querySelector(`script[src="${src}"]`)) return;
    const script = document.createElement("script");
    script.src = src;
    script.type = "module";
    document.head.appendChild(script);
  }, [captchaEnabled]);

  // The widget solves itself once it is ready (auto="onload") and reports the
  // payload. Its own events are the only reliable readiness signal: the element
  // upgrades before Svelte attaches verify(), so calling it directly races.
  useEffect(() => {
    const el = widgetRef.current;
    if (!captchaEnabled || !el) return;

    const onVerified = (e: Event) => {
      setCaptchaToken((e as CustomEvent<{ payload: string }>).detail?.payload ?? null);
    };
    const onStateChange = (e: Event) => {
      const { state } = (e as CustomEvent<{ state: string }>).detail ?? {};
      if (state === "error" || state === "expired") {
        console.error("captcha: challenge %s", state);
        setCaptchaToken(null);
      }
    };

    el.addEventListener("verified", onVerified);
    el.addEventListener("statechange", onStateChange);
    return () => {
      el.removeEventListener("verified", onVerified);
      el.removeEventListener("statechange", onStateChange);
    };
  }, [captchaEnabled]);

  function resetCaptcha() {
    setCaptchaToken(null);
    const el = widgetRef.current;
    el?.reset?.();
    void el?.verify?.();
  }

  const captchaSolved = !captchaEnabled || !!captchaToken;

  return { captchaEnabled, captchaToken, widgetRef, resetCaptcha, captchaSolved };
}
