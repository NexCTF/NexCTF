import { ExternalLink } from "lucide-react";
import { useTranslation } from "react-i18next";
import { DetailSection } from "@/components/detail-page";
import { EmptyCell } from "@/components/table-cells";
import type { CustomFieldValue } from "@/lib/api";

function CfvValue({ cfv }: { cfv: CustomFieldValue }) {
  if (!cfv.value) return <EmptyCell />;
  if (cfv.definition.field_type === "url") {
    return (
      <a
        href={cfv.value}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 text-link hover:underline"
      >
        {cfv.value}
        <ExternalLink className="size-3 opacity-60" />
      </a>
    );
  }
  return <>{cfv.value}</>;
}

export function CustomFieldValuesList({ values }: { values: CustomFieldValue[] }) {
  const { t } = useTranslation();

  if (values.length === 0) return null;

  return (
    <DetailSection title={t("admin.custom_fields.values_title")}>
      <div className="rounded-lg border divide-y text-sm">
        {values.map((cfv) => (
          <div key={cfv.id} className="flex items-center gap-2 px-4 py-3">
            <span className="text-muted-foreground w-40 shrink-0">{cfv.definition.label}</span>
            <span className="flex-1">
              <CfvValue cfv={cfv} />
            </span>
          </div>
        ))}
      </div>
    </DetailSection>
  );
}
