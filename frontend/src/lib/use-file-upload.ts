import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { apiErrorMessage, type UploadedFile, uploadAdminFile } from "@/lib/api";

/** Warn when an uploaded file's content is already stored under other names. */
export function useDuplicateWarning(): (file: UploadedFile) => void {
  const { t } = useTranslation();
  return (file) => {
    if (file.duplicates.length === 0) return;
    toast.warning(
      t("files.duplicate_upload", {
        name: file.name,
        existing: file.duplicates.map((d) => d.name).join(", "),
        defaultValue: '"{{name}}" has the same content as: {{existing}}',
      }),
    );
  };
}

/** Upload files one after another, warning about any whose content is already stored. */
export function useFileUpload(isPublic: boolean) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const warnDuplicate = useDuplicateWarning();

  return useMutation({
    mutationFn: async (files: File[]): Promise<UploadedFile[]> => {
      const uploaded: UploadedFile[] = [];
      for (const file of files) uploaded.push(await uploadAdminFile(file.name, file, isPublic));
      return uploaded;
    },
    onSuccess: (uploaded) => {
      for (const file of uploaded) warnDuplicate(file);
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(err, t("admin.files.upload_error", { defaultValue: "Upload failed" })),
      ),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["admin", "files"] }),
  });
}
