import { useMutation } from "@tanstack/react-query";
import { Paperclip, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { FilePickerDialog } from "@/components/file-picker-dialog";
import { Button } from "@/components/ui/button";
import { apiErrorMessage, type StoredFile } from "@/lib/api";
import { formatBytes } from "@/lib/utils";

interface AttachedFilesProps {
  title: string;
  files: StoredFile[];
  /** Persist the new set of attached file ids. */
  onSave: (fileIds: string[]) => Promise<unknown>;
}

/** Files attached to a challenge or question, with a picker to change them. */
export function AttachedFiles({ title, files, onSave }: AttachedFilesProps) {
  const { t } = useTranslation();

  const detach = useMutation({
    mutationFn: (id: string) => onSave(files.filter((f) => f.id !== id).map((f) => f.id)),
    onError: (err) =>
      toast.error(
        apiErrorMessage(
          err,
          t("files.attached.error", { defaultValue: "Could not update the files" }),
        ),
      ),
  });

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {title} ({files.length})
        </span>
        <FilePickerDialog
          multiple
          title={t("files.attached.pick_title", { defaultValue: "Attach files" })}
          initialSelected={files}
          confirmLabel={(n) =>
            t("files.attached.save", { n, defaultValue: "Attach {{n}} file(s)" })
          }
          onConfirm={async (picked) => {
            await onSave(picked.map((f) => f.id));
            toast.success(t("files.attached.saved", { defaultValue: "Files updated" }));
          }}
          trigger={
            <Button variant="outline" size="sm" className="h-7 text-xs">
              <Paperclip className="size-3" />
              {t("files.attached.manage", { defaultValue: "Manage files" })}
            </Button>
          }
        />
      </div>
      {files.length === 0 ? (
        <p className="py-1 text-xs text-muted-foreground">
          {t("files.attached.empty", { defaultValue: "No files attached." })}
        </p>
      ) : (
        <ul className="space-y-1">
          {files.map((file) => (
            <li key={file.id} className="flex items-center gap-2 rounded-md border px-3 py-1.5">
              <Paperclip className="size-3 shrink-0 text-muted-foreground" />
              <span className="flex-1 truncate text-xs font-medium">{file.name}</span>
              <span className="text-xs text-muted-foreground">{formatBytes(file.file_size)}</span>
              <Button
                variant="ghost"
                size="icon-xs"
                disabled={detach.isPending}
                aria-label={t("files.attached.detach", {
                  name: file.name,
                  defaultValue: "Detach {{name}}",
                })}
                onClick={() => detach.mutate(file.id)}
              >
                <X className="size-3" />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
