import { Check, Copy, FileText } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, buttonVariants } from "@/components/ui/button";
import type { PublicFile } from "@/lib/api";
import { copyToClipboard, formatBytes } from "@/lib/utils";

function CopyHashButton({ file }: { file: PublicFile }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  if (!file.sha256) return null;
  const sha256 = file.sha256;

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon-sm"
      title={`SHA-256 ${sha256}`}
      aria-label={t("challenge.copy_sha256", {
        name: file.name,
        defaultValue: "Copy the SHA-256 of {{name}}",
      })}
      onClick={() => {
        copyToClipboard(sha256);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
    >
      {copied ? <Check className="text-green-600" /> : <Copy />}
    </Button>
  );
}

/** Download buttons for a challenge's or question's files, with their SHA-256. */
export function PlayerFileList({ files }: { files: PublicFile[] }) {
  const { t } = useTranslation();
  if (files.length === 0) return null;

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {t("challenge.files")}
      </p>
      <div className="flex flex-wrap gap-2">
        {files.map((f) => (
          <span key={f.id} className="inline-flex items-center">
            <a
              href={f.url}
              target="_blank"
              rel="noreferrer"
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              <FileText className="text-muted-foreground" />
              {f.name}
              {f.file_size != null && (
                <span className="text-xs text-muted-foreground">({formatBytes(f.file_size)})</span>
              )}
            </a>
            <CopyHashButton file={f} />
          </span>
        ))}
      </div>
    </div>
  );
}
