import { Eye, Pencil } from "lucide-react";
import type * as React from "react";
import { useState } from "react";
import { Markdown } from "@/components/markdown";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

interface MarkdownEditorProps {
  value: string;
  onChange: (value: string) => void;
  rows?: number;
  required?: boolean;
  id?: string;
  placeholder?: string;
  ref?: React.Ref<HTMLTextAreaElement>;
}

export function MarkdownEditor({
  value,
  onChange,
  rows = 4,
  required,
  id,
  placeholder,
  ref,
}: MarkdownEditorProps) {
  const [previewing, setPreviewing] = useState(false);

  return (
    <div className="rounded-lg border overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center gap-1 px-2 py-1 border-b bg-muted/40">
        <button
          type="button"
          onClick={() => setPreviewing(false)}
          className={cn(
            "flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-colors",
            !previewing
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          <Pencil className="size-3" />
          Write
        </button>
        <button
          type="button"
          onClick={() => setPreviewing(true)}
          className={cn(
            "flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-colors",
            previewing
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          <Eye className="size-3" />
          Preview
        </button>
        <span className="ml-auto text-xs text-muted-foreground">Markdown</span>
      </div>

      {/* Content */}
      {previewing ? (
        <div className="px-3 py-2 min-h-[80px]">
          {value.trim() ? (
            <Markdown>{value}</Markdown>
          ) : (
            <p className="text-sm text-muted-foreground italic">Nothing to preview.</p>
          )}
        </div>
      ) : (
        <Textarea
          ref={ref}
          id={id}
          rows={rows}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          required={required}
          placeholder={placeholder}
          className="rounded-none border-0 focus-visible:ring-0 resize-y"
        />
      )}
    </div>
  );
}
