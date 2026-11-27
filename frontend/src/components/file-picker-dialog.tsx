import { useInfiniteQuery, useMutation } from "@tanstack/react-query";
import { FileText, Globe, Image, Link2, Lock, Upload } from "lucide-react";
import { type ReactElement, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { useUsageSummary } from "@/components/file-usage";
import { SearchInput } from "@/components/search-input";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  apiErrorMessage,
  getAdminFiles,
  markFilePublic,
  type StoredFile,
  type StoredFileListItem,
} from "@/lib/api";
import { useDebouncedValue } from "@/lib/use-debounced-value";
import { useFileUpload } from "@/lib/use-file-upload";
import { cn, formatBytes } from "@/lib/utils";

const PAGE_SIZE = 20;

export interface FilePickerDialogProps {
  /** Element opening the dialog. */
  trigger: ReactElement;
  title: string;
  /** Label of the confirm button, given the number of selected files. */
  confirmLabel: (selected: number) => string;
  /** Pick several files instead of one. */
  multiple?: boolean;
  /** Files selected when the dialog opens. */
  initialSelected?: StoredFile[];
  /** Only list and accept files whose MIME type starts with this, e.g. "image/". */
  mimePrefix?: string;
  /** Upload new files as public, and make picked private files public on confirm. */
  publicOnPick?: boolean;
  onConfirm: (files: StoredFile[]) => unknown;
}

function filesQuery(search: string, mimePrefix: string | undefined, page: number): string {
  const params = new URLSearchParams({
    page: String(page),
    items_per_page: String(PAGE_SIZE),
    order_by: "created_at",
    order: "desc",
  });
  if (search) params.set("search", search);
  if (mimePrefix) params.set("mime_prefix", mimePrefix);
  return params.toString();
}

function FileRow({
  file,
  multiple,
  checked,
  onToggle,
}: {
  file: StoredFileListItem;
  multiple: boolean;
  checked: boolean;
  onToggle: () => void;
}) {
  const { t } = useTranslation();
  const usageSummary = useUsageSummary();
  const isImage = file.mime_type?.startsWith("image/");

  return (
    <label
      className={cn(
        "flex cursor-pointer items-center gap-3 px-3 py-2 hover:bg-muted/60",
        checked && "bg-muted/60",
      )}
    >
      <input
        type={multiple ? "checkbox" : "radio"}
        name="file-picker"
        checked={checked}
        onChange={onToggle}
        aria-label={file.name}
        className="shrink-0"
      />
      {isImage ? (
        <Image className="size-4 shrink-0 text-muted-foreground" />
      ) : (
        <FileText className="size-4 shrink-0 text-muted-foreground" />
      )}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{file.name}</p>
        <p className="truncate font-mono text-xs text-muted-foreground">
          {file.original_filename}
          {file.file_size !== null && ` · ${formatBytes(file.file_size)}`}
        </p>
      </div>
      {file.usages.length > 0 && (
        <span
          className="flex shrink-0 items-center gap-1 text-xs text-muted-foreground"
          title={usageSummary(file.usages)}
        >
          <Link2 className="size-3" />
          {file.usages.length}
        </span>
      )}
      {file.is_public ? (
        <Globe
          className="size-3.5 shrink-0 text-green-600"
          aria-label={t("files.public", { defaultValue: "Public" })}
        />
      ) : (
        <Lock
          className="size-3.5 shrink-0 text-muted-foreground"
          aria-label={t("files.private", { defaultValue: "Private" })}
        />
      )}
    </label>
  );
}

function useFilePages(open: boolean, search: string, mimePrefix: string | undefined) {
  const query = useInfiniteQuery({
    queryKey: ["admin", "files", "picker", search, mimePrefix ?? ""],
    queryFn: ({ pageParam }) => getAdminFiles(filesQuery(search, mimePrefix, pageParam)),
    initialPageParam: 1,
    getNextPageParam: (last) => (last.pagination.has_more ? last.pagination.page + 1 : undefined),
    enabled: open,
  });
  const files = useMemo(() => query.data?.pages.flatMap((p) => p.data) ?? [], [query.data]);
  return { query, files };
}

/** Search, upload and pick stored files, for attachments, markdown and image fields. */
export function FilePickerDialog({
  trigger,
  title,
  confirmLabel,
  multiple = false,
  initialSelected = [],
  mimePrefix,
  publicOnPick = false,
  onConfirm,
}: FilePickerDialogProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [searchInput, setSearchInput] = useState("");
  const search = useDebouncedValue(searchInput.trim(), 250);
  const [selected, setSelected] = useState<Map<string, StoredFile>>(new Map());
  const [dragging, setDragging] = useState(false);
  const uploadRef = useRef<HTMLInputElement>(null);
  const { query, files } = useFilePages(open, search, mimePrefix);
  const upload = useFileUpload(publicOnPick);

  function handleOpenChange(next: boolean) {
    if (next) {
      setSelected(new Map(initialSelected.map((f) => [f.id, f])));
      setSearchInput("");
    }
    setOpen(next);
  }

  function toggle(file: StoredFile) {
    setSelected((prev) => {
      if (!multiple) return new Map([[file.id, file]]);
      const next = new Map(prev);
      if (next.has(file.id)) next.delete(file.id);
      else next.set(file.id, file);
      return next;
    });
  }

  function accepted(list: File[]): File[] {
    if (!mimePrefix) return list;
    const ok = list.filter((f) => f.type.startsWith(mimePrefix));
    if (ok.length < list.length) {
      toast.error(
        t("files.picker.wrong_type", {
          type: `${mimePrefix}*`,
          defaultValue: "Only {{type}} files can be used here.",
        }),
      );
    }
    return ok;
  }

  function uploadFiles(list: File[]) {
    const wanted = accepted(multiple ? list : list.slice(0, 1));
    if (wanted.length === 0) return;
    upload.mutate(wanted, {
      onSuccess: (uploaded) => {
        for (const file of uploaded) toggle(file);
      },
    });
  }

  const picked = [...selected.values()];
  const privatePicked = publicOnPick ? picked.filter((f) => !f.is_public) : [];

  const confirm = useMutation({
    mutationFn: async () => {
      const files = await Promise.all(
        picked.map((f) => (publicOnPick && !f.is_public ? markFilePublic(f.id, true) : f)),
      );
      await onConfirm(files);
    },
    onSuccess: () => setOpen(false),
    onError: (err) =>
      toast.error(
        apiErrorMessage(err, t("files.picker.error", { defaultValue: "Could not use the files" })),
      ),
  });

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger render={trigger} />
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>

        <input
          ref={uploadRef}
          type="file"
          multiple={multiple}
          accept={mimePrefix ? `${mimePrefix}*` : undefined}
          className="hidden"
          data-testid="file-picker-upload"
          onChange={(e) => {
            const list = Array.from(e.target.files ?? []);
            e.target.value = "";
            uploadFiles(list);
          }}
        />

        <div className="flex gap-2">
          <SearchInput
            value={searchInput}
            onValueChange={setSearchInput}
            placeholder={t("common.search", { defaultValue: "Search…" })}
            aria-label={t("common.search", { defaultValue: "Search…" })}
          />
          <Button
            type="button"
            variant="outline"
            disabled={upload.isPending}
            onClick={() => uploadRef.current?.click()}
          >
            <Upload className="size-3.5" />
            {upload.isPending
              ? t("admin.files.uploading", { defaultValue: "Uploading…" })
              : t("files.picker.upload", { defaultValue: "Upload" })}
          </Button>
        </div>

        <section
          aria-label={t("files.picker.list", { defaultValue: "Stored files" })}
          className={cn(
            "max-h-80 divide-y overflow-y-auto rounded-md border",
            dragging && "border-primary bg-primary/5",
          )}
          onDragOver={(e) => {
            if (!e.dataTransfer.types.includes("Files")) return;
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            uploadFiles(Array.from(e.dataTransfer.files));
          }}
        >
          {query.isLoading ? (
            <p className="p-4 text-center text-sm text-muted-foreground">{t("common.loading")}</p>
          ) : files.length === 0 ? (
            <p className="p-4 text-center text-sm text-muted-foreground">
              {t("files.picker.empty", {
                defaultValue: "No files found. Upload one or drop it here.",
              })}
            </p>
          ) : (
            files.map((file) => (
              <FileRow
                key={file.id}
                file={file}
                multiple={multiple}
                checked={selected.has(file.id)}
                onToggle={() => toggle(file)}
              />
            ))
          )}
          {query.hasNextPage && (
            <div className="p-2 text-center">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={query.isFetchingNextPage}
                onClick={() => void query.fetchNextPage()}
              >
                {t("files.picker.more", { defaultValue: "Load more" })}
              </Button>
            </div>
          )}
        </section>
        <p className="text-xs text-muted-foreground">
          {t("files.picker.drop_hint", { defaultValue: "Drop files on the list to upload them." })}
        </p>

        {privatePicked.length > 0 && (
          <p className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
            {t("files.picker.will_publish", {
              names: privatePicked.map((f) => f.name).join(", "),
              defaultValue:
                "{{names}} will be made public: anyone with the link can download it, even before the challenge opens.",
            })}
          </p>
        )}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => setOpen(false)}>
            {t("common.cancel")}
          </Button>
          <Button
            type="button"
            disabled={confirm.isPending || upload.isPending || (!multiple && picked.length === 0)}
            onClick={() => confirm.mutate()}
          >
            {confirmLabel(picked.length)}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
