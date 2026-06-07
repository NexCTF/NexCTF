import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { getPublicInfo } from "@/lib/api";

function formatDate(iso: string): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString(undefined, { dateStyle: "long", timeStyle: "short" });
}

function formatCountdown(
  iso: string,
  pastLabel: string,
  unitD: string,
  unitH: string,
  unitM: string,
  unitS: string,
): string {
  if (!iso) return "";
  const delta = new Date(iso).getTime() - Date.now();
  if (delta <= 0) return pastLabel;

  const s = Math.floor(delta / 1000) % 60;
  const m = Math.floor(delta / 60_000) % 60;
  const h = Math.floor(delta / 3_600_000) % 24;
  const d = Math.floor(delta / 86_400_000);

  const parts: string[] = [];
  if (d > 0) parts.push(`${d}${unitD}`);
  if (d > 0 || h > 0) parts.push(`${h}${unitH}`);
  if (d > 0 || h > 0 || m > 0) parts.push(`${m}${unitM}`);
  parts.push(`${s}${unitS}`);
  return parts.join(" ");
}

export function useMagicVars(): Record<string, string> {
  const { t } = useTranslation();
  const { data: info } = useQuery({
    queryKey: ["info", "public"],
    queryFn: getPublicInfo,
    staleTime: 5 * 60 * 1000,
  });

  const [, tick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const branding = info?.branding;
  const competition = info?.competition;
  const startIso = competition?.start_time ?? "";
  const endIso = competition?.end_time ?? "";

  const unitD = t("pages.magic.unit_d", { defaultValue: "d" });
  const unitH = t("pages.magic.unit_h", { defaultValue: "h" });
  const unitM = t("pages.magic.unit_m", { defaultValue: "m" });
  const unitS = t("pages.magic.unit_s", { defaultValue: "s" });

  return {
    event_name: branding?.name ?? "",
    event_start: formatDate(startIso),
    event_end: formatDate(endIso),
    countdown_to_start: formatCountdown(
      startIso,
      t("pages.magic.started", { defaultValue: "Started" }),
      unitD,
      unitH,
      unitM,
      unitS,
    ),
    countdown_to_end: formatCountdown(
      endIso,
      t("pages.magic.ended", { defaultValue: "Ended" }),
      unitD,
      unitH,
      unitM,
      unitS,
    ),
  };
}
