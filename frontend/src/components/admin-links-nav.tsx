import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { useTranslation } from "react-i18next";
import { getAdminLinks } from "@/lib/api";

/** Sidebar section listing enabled admin-visibility Links, as external shortcuts. */
export function AdminLinksNav({ itemClassName }: { itemClassName: string }) {
  const { t } = useTranslation();

  const { data: linksResponse } = useQuery({
    queryKey: ["admin", "links", "quicklinks"],
    queryFn: () => getAdminLinks("items_per_page=100"),
    staleTime: 60 * 1000,
  });
  const quickLinks = (linksResponse?.data ?? []).filter(
    (l) => l.is_enabled && l.visibility === "admin",
  );

  if (quickLinks.length === 0) return null;

  return (
    <div>
      <p className="mb-1 px-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60">
        {t("admin.nav.section.links", { defaultValue: "Links" })}
      </p>
      <div className="space-y-0.5">
        {quickLinks.map((l) => (
          <a
            key={l.id}
            href={l.url}
            target="_blank"
            rel="noopener noreferrer"
            className={itemClassName}
          >
            <ExternalLink className="h-4 w-4 shrink-0" />
            {l.name}
          </a>
        ))}
      </div>
    </div>
  );
}
