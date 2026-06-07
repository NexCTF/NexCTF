import { useMutation } from "@tanstack/react-query";
import { Pencil } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { CustomFieldInput } from "@/components/custom-field-input";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  apiErrorMessage,
  type CustomFieldDefinition,
  type CustomFieldValue,
  setAdminCustomFieldValue,
} from "@/lib/api";

interface SetCustomFieldValueDialogProps {
  entityId: string;
  entityType: "user" | "team";
  field: Pick<CustomFieldDefinition, "id" | "label" | "field_type">;
  existing: CustomFieldValue | undefined;
  onSaved: () => void;
}

export function SetCustomFieldValueDialog({
  entityId,
  entityType,
  field,
  existing,
  onSaved,
}: SetCustomFieldValueDialogProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState(existing?.value ?? "");

  const mutation = useMutation({
    mutationFn: () =>
      setAdminCustomFieldValue({
        definition_id: field.id,
        [entityType === "user" ? "user_id" : "team_id"]: entityId,
        value: value || null,
      }),
    onSuccess: () => {
      toast.success(t("admin.custom_fields.value_saved"));
      setOpen(false);
      onSaved();
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.custom_fields.value_save_error"))),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button variant="ghost" size="icon" className="size-7">
            <Pencil className="size-3.5" />
          </Button>
        }
      />
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>{field.label}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
          className="space-y-4 mt-2"
        >
          <div className="space-y-1.5">
            <Label>{t("admin.custom_fields.value_label")}</Label>
            <CustomFieldInput fieldType={field.field_type} value={value} onChange={setValue} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? t("common.saving") : t("common.save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
