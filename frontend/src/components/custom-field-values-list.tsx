import { ExternalLink, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { DetailSection } from "@/components/detail-page";
import { SetCustomFieldValueDialog } from "@/components/set-custom-field-value-dialog";
import { Button } from "@/components/ui/button";
import { apiErrorMessage, type CustomFieldValue, deleteAdminCustomFieldValue } from "@/lib/api";

interface CustomFieldValuesListProps {
  entityId: string;
  entityType: "user" | "team";
  values: CustomFieldValue[];
  onSaved: () => void;
  readOnly?: boolean;
}

function CfvValue({ cfv }: { cfv: CustomFieldValue }) {
  if (!cfv.value) return <span className="text-muted-foreground">—</span>;
  if (cfv.definition.field_type === "url") {
    return (
      <a
        href={cfv.value}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 text-primary hover:underline"
      >
        {cfv.value}
        <ExternalLink className="size-3 opacity-60" />
      </a>
    );
  }
  return <>{cfv.value}</>;
}

export function CustomFieldValuesList({
  entityId,
  entityType,
  values,
  onSaved,
  readOnly = false,
}: CustomFieldValuesListProps) {
  const { t } = useTranslation();

  if (values.length === 0) return null;

  function handleDelete(id: string) {
    if (!confirm(t("admin.custom_fields.value_delete_confirm"))) return;
    void deleteAdminCustomFieldValue(id)
      .then(onSaved)
      .catch((err) => toast.error(apiErrorMessage(err, t("admin.custom_fields.value_save_error"))));
  }

  return (
    <DetailSection title={t("admin.custom_fields.values_title")}>
      <div className="rounded-lg border divide-y text-sm">
        {values.map((cfv) => (
          <div key={cfv.id} className="flex items-center gap-2 px-4 py-3">
            <span className="text-muted-foreground w-40 shrink-0">{cfv.definition.label}</span>
            <span className="flex-1">
              <CfvValue cfv={cfv} />
            </span>
            {!readOnly && (
              <div className="flex gap-1 shrink-0">
                <SetCustomFieldValueDialog
                  entityId={entityId}
                  entityType={entityType}
                  field={cfv.definition}
                  existing={cfv}
                  onSaved={onSaved}
                />
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-7 text-destructive hover:text-destructive"
                  onClick={() => handleDelete(cfv.id)}
                >
                  <Trash2 className="size-3.5" />
                </Button>
              </div>
            )}
          </div>
        ))}
      </div>
    </DetailSection>
  );
}
