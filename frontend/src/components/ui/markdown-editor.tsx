import { Eye, Paperclip, Pencil } from "lucide-react";
import type * as React from "react";
import { useImperativeHandle, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { FilePickerDialog } from "@/components/file-picker-dialog";
import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { StoredFile } from "@/lib/api";
import { useFileUpload } from "@/lib/use-file-upload";
import { cn } from "@/lib/utils";

export interface MarkdownEditorHandle {
  insert: (text: string) => void;
}

interface MarkdownEditorProps {
  value: string;
  onChange: (value: string) => void;
  rows?: number;
  required?: boolean;
  id?: string;
  placeholder?: string;
  ref?: React.Ref<MarkdownEditorHandle>;
}

/** Whether a paste comes from a document editor, which puts a picture of the text beside it. */
function isRichTextPaste(data: DataTransfer): boolean {
  return data.types.includes("text/html") || data.types.includes("text/rtf");
}

export function fileMarkdown(file: StoredFile): string {
  const url = `/api/v1/file/${file.id}/view`;
  if (file.mime_type?.startsWith("image/")) return `![${file.name}](${url})`;
  // The view URL has no extension, so media files carry their filename in the
  // fragment — that is what the renderer matches on to embed a player.
  const isMedia = /^(video|audio)\//.test(file.mime_type ?? "");
  const suffix = isMedia ? `#${encodeURIComponent(file.original_filename)}` : "";
  return `[${file.name}](${url}${suffix})`;
}

function InsertFileButton({ onInsert }: { onInsert: (markdown: string) => void }) {
  const { t } = useTranslation();
  return (
    <FilePickerDialog
      publicOnPick
      title={t("markdown.pick_file", { defaultValue: "Pick a file to insert" })}
      confirmLabel={() => t("markdown.insert", { defaultValue: "Insert" })}
      onConfirm={([file]) => file && onInsert(fileMarkdown(file))}
      trigger={
        <Button type="button" variant="ghost" size="sm" className="h-auto px-2.5 py-1 text-xs">
          <Paperclip className="size-3 mr-1.5" />
          {t("markdown.insert_file", { defaultValue: "Insert file" })}
        </Button>
      }
    />
  );
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
  const { t } = useTranslation();
  const [previewing, setPreviewing] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const upload = useFileUpload(true);
  const valueRef = useRef(value);
  valueRef.current = value;

  function uploadAndInsert(files: FileList | null): boolean {
    const list = Array.from(files ?? []);
    if (list.length === 0) return false;
    upload.mutate(list, {
      onSuccess: (uploaded) => {
        insert(uploaded.map(fileMarkdown).join("\n"));
        toast.info(
          t("markdown.uploaded_public", {
            defaultValue: "Uploaded as public: anyone with the link can download it.",
          }),
        );
      },
    });
    return true;
  }

  function insert(text: string) {
    setPreviewing(false);
    const value = valueRef.current;
    const ta = textareaRef.current;
    if (!ta) {
      onChange(value + (value.endsWith("\n") || !value ? "" : "\n") + text);
      return;
    }
    const { selectionStart: start, selectionEnd: end } = ta;
    onChange(value.slice(0, start) + text + value.slice(end));
    setTimeout(() => {
      ta.focus();
      ta.setSelectionRange(start + text.length, start + text.length);
    }, 0);
  }

  useImperativeHandle(ref, () => ({ insert }));

  return (
    <div className="rounded-lg border overflow-hidden">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-1 px-2 py-1 border-b bg-muted/40">
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
          {t("markdown.write", { defaultValue: "Write" })}
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
          {t("markdown.preview", { defaultValue: "Preview" })}
        </button>
        <div className="ml-auto">
          {upload.isPending && (
            <span className="mr-2 text-xs text-muted-foreground">
              {t("admin.files.uploading", { defaultValue: "Uploading…" })}
            </span>
          )}
          <InsertFileButton onInsert={insert} />
        </div>
      </div>

      {/* Content */}
      {previewing ? (
        <div className="px-3 py-2 min-h-[80px]">
          {value.trim() ? (
            <Markdown>{value}</Markdown>
          ) : (
            <p className="text-sm text-muted-foreground italic">
              {t("markdown.nothing_to_preview", { defaultValue: "Nothing to preview." })}
            </p>
          )}
        </div>
      ) : (
        <Textarea
          ref={textareaRef}
          id={id}
          rows={rows}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onPaste={(e) => {
            if (isRichTextPaste(e.clipboardData)) return;
            if (uploadAndInsert(e.clipboardData.files)) e.preventDefault();
          }}
          onDragOver={(e) => {
            if (e.dataTransfer.types.includes("Files")) e.preventDefault();
          }}
          onDrop={(e) => {
            if (uploadAndInsert(e.dataTransfer.files)) e.preventDefault();
          }}
          required={required}
          placeholder={placeholder}
          className="rounded-none border-0 focus-visible:ring-0 resize-y"
        />
      )}
    </div>
  );
}
