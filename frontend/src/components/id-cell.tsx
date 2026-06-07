import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { cn, copyToClipboard } from "@/lib/utils";

interface IdCellProps {
  id: string;
}

export function IdCell({ id }: IdCellProps) {
  const [copied, setCopied] = useState(false);

  function handleCopy(e: React.MouseEvent) {
    e.stopPropagation();
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
      aria-label="Copy ID"
    >
      {short}
      {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
    </button>
  );
}
