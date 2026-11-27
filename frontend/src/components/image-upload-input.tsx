import { ImageOff, Upload, X } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { FilePickerDialog } from "@/components/file-picker-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { publicFileUrl } from "@/lib/api";

interface ImageUploadInputProps {
  value: string;
  onChange: (value: string) => void;
}

/** URL field for an image, with a picker that uploads or reuses a stored image. */
export function ImageUploadInput({ value, onChange }: ImageUploadInputProps) {
  const { t } = useTranslation();
  const [broken, setBroken] = useState(false);

  return (
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
      <FilePickerDialog
        publicOnPick
        mimePrefix="image/"
        title={t("files.image_picker.title", { defaultValue: "Choose an image" })}
        confirmLabel={() => t("files.image_picker.use", { defaultValue: "Use image" })}
        onConfirm={([file]) => {
          if (!file) return;
          setBroken(false);
          onChange(publicFileUrl(file.id));
        }}
        trigger={
          <Button type="button" variant="outline" size="lg">
            <Upload />
            {t("files.image_picker.open", { defaultValue: "Choose" })}
          </Button>
        }
      />
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
  );
}
