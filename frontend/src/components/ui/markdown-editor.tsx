import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, Image, Link2, Paperclip, Pencil, Upload } from "lucide-react";
import type * as React from "react";
import { useImperativeHandle, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  apiErrorMessage,
  getAdminFiles,
  markFilePublic,
  type StoredFile,
  uploadAdminFile,
} from "@/lib/api";
import { cn, formatBytes } from "@/lib/utils";

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

export function fileMarkdown(file: StoredFile): string {
  const url = `/api/v1/file/${file.id}/view`;
  if (file.mime_type?.startsWith("image/")) return `![${file.name}](${url})`;
  // The view URL has no extension, so media files carry their filename in the
  // fragment — that is what the renderer matches on to embed a player.
  const isMedia = /^(video|audio)\//.test(file.mime_type ?? "");
  const suffix = isMedia ? `#${encodeURIComponent(file.original_filename)}` : "";
  return `[${file.name}](${url}${suffix})`;
}

function FilePicker({ onInsert }: { onInsert: (markdown: string) => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [pending, setPending] = useState<{ file: File; name: string } | null>(null);
  const uploadRef = useRef<HTMLInputElement>(null);

  const { data: filesResponse } = useQuery({
    queryKey: ["admin", "files", "picker", search],
    queryFn: () => getAdminFiles(search ? `search=${encodeURIComponent(search)}` : ""),
    enabled: open,
  });

  const markPublicMutation = useMutation({
    mutationFn: (fileId: string) => markFilePublic(fileId, true),
    onError: (err) =>
      toast.error(
        apiErrorMessage(
          err,
          t("markdown.make_public_error", { defaultValue: "Failed to make file public" }),
        ),
      ),
  });

  function pick(file: StoredFile) {
    onInsert(fileMarkdown(file));
    setOpen(false);
    setSearch("");
    setPending(null);
  }

  const uploadMutation = useMutation({
    mutationFn: ({ file, name }: { file: File; name: string }) => uploadAdminFile(name, file, true),
    onSuccess: (file) => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "files"] });
      pick(file);
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(err, t("admin.files.upload_error", { defaultValue: "Upload failed" })),
      ),
  });

  async function handlePick(file: StoredFile) {
    if (!file.is_public) {
      try {
        await markPublicMutation.mutateAsync(file.id);
      } catch {
        return;
      }
    }
    pick(file);
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button type="button" variant="ghost" size="sm" className="h-auto px-2.5 py-1 text-xs">
            <Paperclip className="size-3 mr-1.5" />
            {t("markdown.insert_file", { defaultValue: "Insert file" })}
          </Button>
        }
      />
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>
            {t("markdown.pick_file", { defaultValue: "Pick a file to insert" })}
          </DialogTitle>
        </DialogHeader>
        <input
          ref={uploadRef}
          type="file"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) setPending({ file, name: file.name });
          }}
        />
        {pending ? (
          <form
            className="space-y-2"
            onSubmit={(e) => {
              e.preventDefault();
              uploadMutation.mutate(pending);
            }}
          >
            <Label htmlFor="picker-upload-name">
              {t("admin.files.field_name", { defaultValue: "Name" })}
            </Label>
            <Input
              id="picker-upload-name"
              value={pending.name}
              onChange={(e) => setPending({ ...pending, name: e.target.value })}
              required
            />
            <p className="text-xs text-muted-foreground font-mono truncate">{pending.file.name}</p>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setPending(null)}>
                {t("common.cancel", { defaultValue: "Cancel" })}
              </Button>
              <Button type="submit" disabled={uploadMutation.isPending}>
                {uploadMutation.isPending
                  ? t("admin.files.uploading", { defaultValue: "Uploading…" })
                  : t("admin.files.upload_btn", { defaultValue: "Upload" })}
              </Button>
            </div>
          </form>
        ) : (
          <>
            <div className="flex gap-2 mb-2">
              <Input
                placeholder={t("common.search", { defaultValue: "Search…" })}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <Button type="button" variant="outline" onClick={() => uploadRef.current?.click()}>
                <Upload className="size-3.5 mr-1.5" />
                {t("markdown.upload_file", { defaultValue: "Upload" })}
              </Button>
            </div>
            <div className="max-h-80 overflow-y-auto divide-y rounded border">
              {!filesResponse?.data?.length ? (
                <p className="p-4 text-sm text-muted-foreground text-center">
                  {t("markdown.no_files", {
                    defaultValue: "No files found. Upload files first in the Files section.",
                  })}
                </p>
              ) : (
                filesResponse.data.map((file) => (
                  <button
                    key={file.id}
                    type="button"
                    className="w-full flex items-start gap-3 px-3 py-2.5 text-left hover:bg-muted/60 transition-colors"
                    onClick={() => handlePick(file)}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{file.name}</p>
                      <p className="text-xs text-muted-foreground font-mono truncate">
                        {file.original_filename}
                      </p>
                      {file.mime_type && (
                        <p className="text-xs text-muted-foreground">
                          {file.mime_type}
                          {file.file_size ? ` · ${formatBytes(file.file_size)}` : ""}
                          {!file.is_public && (
                            <span className="ml-2 text-amber-600">
                              {t("markdown.will_make_public", {
                                defaultValue: "will be made public",
                              })}
                            </span>
                          )}
                        </p>
                      )}
                    </div>
                    {file.mime_type?.startsWith("image/") ? (
                      <Image className="size-4 shrink-0 text-muted-foreground mt-0.5" />
                    ) : (
                      <Link2 className="size-4 shrink-0 text-muted-foreground mt-0.5" />
                    )}
                  </button>
                ))
              )}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
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

  function insert(text: string) {
    setPreviewing(false);
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
          <FilePicker onInsert={insert} />
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
          required={required}
          placeholder={placeholder}
          className="rounded-none border-0 focus-visible:ring-0 resize-y"
        />
      )}
    </div>
  );
}
