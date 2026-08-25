import { useQuery } from "@tanstack/react-query";
import type { Dispatch, SetStateAction } from "react";
import { useTranslation } from "react-i18next";
import { CustomFieldInput } from "@/components/custom-field-input";
import { Label } from "@/components/ui/label";
import { type CustomFieldDefinition, getAdminCustomFields } from "@/lib/api";

/** Definitions for one target, fetched once *enabled* (usually a dialog opening). */
export function useCustomFieldDefs(
  target: CustomFieldDefinition["target"],
  enabled: boolean,
): CustomFieldDefinition[] {
  const { data } = useQuery({
    queryKey: ["admin", "custom-fields", "all"],
    queryFn: () => getAdminCustomFields("items_per_page=100"),
    enabled,
  });
  return (data?.data ?? []).filter((d) => d.target === target);
}

/** The subset of a definition the form needs, so profile payloads fit too. */
export type CustomFieldFormDef = Pick<
  CustomFieldDefinition,
  "id" | "label" | "field_type" | "is_required"
>;

interface CustomFieldsSectionProps {
  defs: CustomFieldFormDef[];
  values: Record<string, string>;
  onChange: Dispatch<SetStateAction<Record<string, string>>>;
  title?: string;
}

export function CustomFieldsSection({ defs, values, onChange, title }: CustomFieldsSectionProps) {
  const { t } = useTranslation();

  if (defs.length === 0) return null;

  return (
    <div className="space-y-3">
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title ?? t("admin.custom_fields.values_title")}
      </p>
      {defs.map((def) => (
        <div key={def.id} className="space-y-1.5">
          <Label htmlFor={`custom-field-${def.id}`}>
            {def.label}
            {def.is_required && <span className="text-destructive ml-0.5">*</span>}
          </Label>
          <CustomFieldInput
            id={`custom-field-${def.id}`}
            fieldType={def.field_type}
            value={values[def.id] ?? ""}
            onChange={(v) => onChange((prev) => ({ ...prev, [def.id]: v }))}
          />
        </div>
      ))}
    </div>
  );
}
