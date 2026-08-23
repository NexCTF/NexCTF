import { useTranslation } from "react-i18next";
import { StatusBadge } from "@/components/status-badge";

/** Question scoring: points in green, malus in red. A malus of 0 is no malus, so it is hidden. */
export function PointsBadges({ points, malus }: { points: number; malus: number | null }) {
  const { t } = useTranslation();

  return (
    <span className="shrink-0 inline-flex items-center gap-1">
      <StatusBadge tone="green" title={t("common.points_hint")}>
        {t("common.points", { value: points })}
      </StatusBadge>
      {malus != null && malus > 0 && (
        <StatusBadge tone="red" title={t("common.malus_hint")}>
          {t("common.points", { value: malus })}
        </StatusBadge>
      )}
    </span>
  );
}
