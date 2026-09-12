import { useTranslation } from "react-i18next";
import { StatusBadge } from "@/components/status-badge";

/** Marks a feature as not yet stable. */
export function BetaBadge() {
  const { t } = useTranslation();
  return <StatusBadge tone="amber">{t("common.beta", { defaultValue: "Beta" })}</StatusBadge>;
}
