import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { stopRowClick } from "@/components/table-cells";
import { cn, copyToClipboard } from "@/lib/utils";

interface IdCellProps {
  id: string;
}

export function IdCell({ id }: IdCellProps) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  function handleCopy(e: React.MouseEvent) {
    stopRowClick(e);
    copyToClipboard(id);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  const short = id.split("-")[0];

  return (
    <button
      type="button"
      onClick={handleCopy}
      className={cn(
        "flex items-center gap-1.5 font-mono text-xs text-muted-foreground rounded px-1 -mx-1 transition-colors hover:bg-muted hover:text-foreground",
        copied && "text-green-500",
      )}
      aria-label={t("table.copy_id", { defaultValue: "Copy ID" })}
    >
      {short}
      {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
    </button>
  );
}
