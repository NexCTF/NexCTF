import { Trash2 } from "lucide-react";
import { type ReactElement, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

type ConfirmDialogProps = {
  /** Element opening the dialog. Rendered as the trigger. */
  trigger: ReactElement;
  /** What the confirmation is about. */
  description: string;
  confirmLabel?: string;
  /** Styles the confirm button as destructive. Off for actions that only spend. */
  destructive?: boolean;
  onConfirm: () => void;
};

export function ConfirmDialog({
  trigger,
  description,
  confirmLabel,
  destructive = true,
  onConfirm,
}: ConfirmDialogProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={trigger} />
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>{t("common.confirm_title", { defaultValue: "Are you sure?" })}</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">{description}</p>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => setOpen(false)}>
            {t("common.cancel")}
          </Button>
          <Button
            type="button"
            variant={destructive ? "destructive" : "default"}
            onClick={() => {
              setOpen(false);
              onConfirm();
            }}
          >
            {confirmLabel ?? t("common.confirm", { defaultValue: "Confirm" })}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Trash icon button guarded by a confirmation dialog. */
export function DeleteButton({
  description,
  onConfirm,
  disabled,
  size = "icon-sm",
  label,
}: {
  description: string;
  onConfirm: () => void;
  disabled?: boolean;
  /** "icon-xs" for compact inline rows. */
  size?: "icon-xs" | "icon-sm";
  /** Accessible name, when "Delete" is not what the action is called. */
  label?: string;
}) {
  const { t } = useTranslation();
  return (
    <ConfirmDialog
      description={description}
      confirmLabel={t("common.delete")}
      onConfirm={onConfirm}
      trigger={
        <Button
          variant="ghost"
          size={size}
          className="text-destructive hover:text-destructive"
          disabled={disabled}
          onClick={(e) => e.stopPropagation()}
          aria-label={label ?? t("common.delete")}
        >
          <Trash2 className={size === "icon-xs" ? "size-3" : "size-3.5"} />
        </Button>
      }
    />
  );
}
