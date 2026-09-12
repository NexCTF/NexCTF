import { useMutation } from "@tanstack/react-query";
import { ImageOff, Upload, X } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiErrorMessage, publicFileUrl, uploadAdminFile } from "@/lib/api";

interface ImageUploadInputProps {
  value: string;
  onChange: (value: string) => void;
}

/** URL field for an image, with an upload button that stores the file in S3. */
export function ImageUploadInput({ value, onChange }: ImageUploadInputProps) {
  const { t } = useTranslation();
  const fileRef = useRef<HTMLInputElement>(null);
  const [broken, setBroken] = useState(false);

  const mutation = useMutation({
    mutationFn: (file: File) => uploadAdminFile(file.name, file, true),
    onSuccess: (file) => {
      setBroken(false);
      onChange(publicFileUrl(file.id));
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(err, t("admin.files.upload_error", { defaultValue: "Upload failed" })),
      ),
  });

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) mutation.mutate(file);
    e.target.value = "";
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3">
        <div className="flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-md border border-input bg-muted/30">
          {value && !broken ? (
            <img
              src={value}
              alt=""
              className="size-full object-contain"
              onError={() => setBroken(true)}
            />
          ) : (
            <ImageOff className="size-4 text-muted-foreground" />
          )}
        </div>
        <Input
          type="text"
          value={value}
          onChange={(e) => {
            setBroken(false);
            onChange(e.target.value);
          }}
          placeholder="https://"
          className="flex-1"
        />
        <Button
          type="button"
          variant="outline"
          size="lg"
          disabled={mutation.isPending}
          onClick={() => fileRef.current?.click()}
        >
          <Upload />
          {mutation.isPending
            ? t("common.uploading", { defaultValue: "Uploading…" })
            : t("common.upload", { defaultValue: "Upload" })}
        </Button>
        {value && (
          <Button
            type="button"
            variant="ghost"
            size="icon-lg"
            aria-label={t("common.clear", { defaultValue: "Clear" })}
            onClick={() => {
              setBroken(false);
              onChange("");
            }}
          >
            <X />
          </Button>
        )}
      </div>
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleFileChange}
      />
    </div>
  );
}
