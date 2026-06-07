import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Download, Eye, FileText, Globe, Lock, Pencil, Plus, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { type Column, DataTable, useTableState } from "@/components/data-table";
import { IdCell } from "@/components/id-cell";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  apiErrorMessage,
  deleteAdminFile,
  getAdminFile,
  getAdminFiles,
  markFilePublic,
  type StoredFile,
  updateAdminFile,
  uploadAdminFile,
} from "@/lib/api";
import { formatBytes } from "@/lib/utils";

export const Route = createFileRoute("/admin/_admin/files")({
  component: FilesPage,
});

// ---------------------------------------------------------------------------
// Upload dialog
// ---------------------------------------------------------------------------

function UploadFileDialog({ onCreated }: { onCreated: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [isPublic, setIsPublic] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const mutation = useMutation({
    // biome-ignore lint/style/noNonNullAssertion: button is disabled when file is null
    mutationFn: () => uploadAdminFile(name, file!, isPublic),
    onSuccess: () => {
      toast.success(t("admin.files.uploaded", { defaultValue: "File uploaded" }));
      setOpen(false);
      setName("");
      setFile(null);
      setIsPublic(false);
      if (fileRef.current) fileRef.current.value = "";
      onCreated();
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(err, t("admin.files.upload_error", { defaultValue: "Upload failed" })),
      ),
  });

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    if (f && !name) setName(f.name);
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button>
            <Plus className="size-4" />
            {t("admin.files.upload", { defaultValue: "Upload file" })}
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("admin.files.upload", { defaultValue: "Upload file" })}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!file) return;
            mutation.mutate();
          }}
          className="space-y-4"
        >
          <div className="space-y-1.5">
            <Label>{t("admin.files.field_file", { defaultValue: "File" })}</Label>
            <Input ref={fileRef} type="file" onChange={handleFileChange} required />
          </div>
          <div className="space-y-1.5">
            <Label>{t("admin.files.field_name", { defaultValue: "Name" })}</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("admin.files.name_placeholder", {
                defaultValue: "Friendly name",
              })}
              required
            />
          </div>
          <div className="flex items-center gap-2">
            <Switch id="upload-public" checked={isPublic} onCheckedChange={setIsPublic} />
            <Label htmlFor="upload-public">
              {t("admin.files.field_public", { defaultValue: "Public (accessible from pages)" })}
            </Label>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {t("common.cancel", { defaultValue: "Cancel" })}
            </Button>
            <Button type="submit" disabled={mutation.isPending || !file}>
              {mutation.isPending
                ? t("common.saving", { defaultValue: "Uploading…" })
                : t("admin.files.upload", { defaultValue: "Upload" })}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Edit / re-upload dialog
// ---------------------------------------------------------------------------

function EditFileDialog({ file, onUpdated }: { file: StoredFile; onUpdated: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(file.name);
  const [upload, setUpload] = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const mutation = useMutation({
    mutationFn: () =>
      updateAdminFile(file.id, {
        name: name !== file.name ? name : undefined,
        file: upload ?? undefined,
      }),
    onSuccess: () => {
      toast.success(t("admin.files.updated", { defaultValue: "File updated" }));
      setOpen(false);
      setUpload(null);
      if (fileRef.current) fileRef.current.value = "";
      onUpdated();
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(err, t("admin.files.update_error", { defaultValue: "Update failed" })),
      ),
  });

  const unchanged = name === file.name && upload === null;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button variant="ghost" size="icon" title="Edit">
            <Pencil className="size-4" />
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("admin.files.edit", { defaultValue: "Edit file" })}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
          className="space-y-4"
        >
          <div className="space-y-1.5">
            <Label>{t("admin.files.field_name", { defaultValue: "Name" })}</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="space-y-1.5">
            <Label>
              {t("admin.files.new_version", {
                defaultValue: "New version (optional)",
              })}
            </Label>
            <Input
              ref={fileRef}
              type="file"
              onChange={(e) => setUpload(e.target.files?.[0] ?? null)}
            />
            <p className="text-xs text-muted-foreground">
              {t("admin.files.new_version_hint", {
                defaultValue:
                  "Upload a new file to replace the current version without changing the ID.",
              })}
            </p>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {t("common.cancel", { defaultValue: "Cancel" })}
            </Button>
            <Button type="submit" disabled={mutation.isPending || unchanged}>
              {mutation.isPending
                ? t("common.saving", { defaultValue: "Saving…" })
                : t("common.save", { defaultValue: "Save" })}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Preview dialog
// ---------------------------------------------------------------------------

type PreviewKind = "image" | "pdf" | "text" | "none";

function resolveKind(mimeType: string | null): PreviewKind {
  if (!mimeType) return "none";
  if (mimeType.startsWith("image/")) return "image";
  if (mimeType === "application/pdf") return "pdf";
  if (
    mimeType.startsWith("text/") ||
    [
      "application/json",
      "application/xml",
      "application/javascript",
      "application/typescript",
      "application/yaml",
    ].includes(mimeType)
  )
    return "text";
  return "none";
}

function PreviewContent({
  kind,
  url,
  filename,
}: {
  kind: PreviewKind;
  url: string;
  filename: string;
}) {
  const [text, setText] = useState<string | null>(null);
  const [textError, setTextError] = useState(false);

  useEffect(() => {
    if (kind !== "text") return;
    fetch(url)
      .then((r) => r.text())
      .then(setText)
      .catch(() => setTextError(true));
  }, [kind, url]);

  if (kind === "image") {
    return (
      <div className="flex items-center justify-center p-2 bg-muted/40 rounded-md min-h-48">
        <img src={url} alt={filename} className="max-h-[60vh] max-w-full object-contain rounded" />
      </div>
    );
  }

  if (kind === "pdf") {
    return (
      <iframe
        src={url}
        title={filename}
        className="w-full rounded border"
        style={{ height: "65vh" }}
      />
    );
  }

  if (kind === "text") {
    if (textError)
      return (
        <p className="text-sm text-destructive">
          Could not load text — check S3 CORS configuration.
        </p>
      );
    if (text === null) return <p className="text-sm text-muted-foreground">Loading…</p>;
    return (
      <pre className="overflow-auto rounded border bg-muted/40 p-3 text-xs max-h-[60vh] whitespace-pre-wrap break-all">
        {text}
      </pre>
    );
  }

  return (
    <div className="flex flex-col items-center gap-3 py-8 text-muted-foreground">
      <FileText className="size-12 opacity-40" />
      <p className="text-sm">No preview available for this file type.</p>
    </div>
  );
}

function PreviewButton({ file }: { file: StoredFile }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const kind = resolveKind(file.mime_type);

  const { data: detail, isLoading } = useQuery({
    queryKey: ["admin", "file-detail", file.id],
    queryFn: () => getAdminFile(file.id),
    enabled: open,
    staleTime: 50 * 60 * 1000, // slightly under 1h presigned URL expiry
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button variant="ghost" size="icon" title="Preview">
            <Eye className="size-4" />
          </Button>
        }
      />
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle className="font-mono text-sm font-normal truncate">
            {file.name}
            <span className="ml-2 text-muted-foreground text-xs">({file.original_filename})</span>
          </DialogTitle>
        </DialogHeader>

        {isLoading || !detail ? (
          <p className="text-sm text-muted-foreground py-8 text-center">
            {t("common.loading", { defaultValue: "Loading…" })}
          </p>
        ) : (
          <PreviewContent kind={kind} url={detail.view_url} filename={file.original_filename} />
        )}

        <div className="flex justify-end pt-1">
          <Button
            variant="outline"
            size="sm"
            onClick={() => detail && window.open(detail.download_url, "_blank")}
            disabled={!detail}
          >
            <Download className="size-3.5 mr-1.5" />
            {t("admin.files.download", { defaultValue: "Download" })}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Public toggle
// ---------------------------------------------------------------------------

function PublicToggle({ file, onUpdated }: { file: StoredFile; onUpdated: () => void }) {
  const { t } = useTranslation();

  const mutation = useMutation({
    mutationFn: () => markFilePublic(file.id, !file.is_public),
    onSuccess: () => onUpdated(),
    onError: (err) =>
      toast.error(
        apiErrorMessage(err, t("admin.files.update_error", { defaultValue: "Update failed" })),
      ),
  });

  return (
    <Button
      variant="ghost"
      size="icon"
      title={
        file.is_public
          ? t("admin.files.make_private", { defaultValue: "Make private" })
          : t("admin.files.make_public", { defaultValue: "Make public" })
      }
      onClick={() => mutation.mutate()}
      disabled={mutation.isPending}
      className={file.is_public ? "text-green-600 hover:text-green-700" : "text-muted-foreground"}
    >
      {file.is_public ? <Globe className="size-4" /> : <Lock className="size-4" />}
    </Button>
  );
}

// ---------------------------------------------------------------------------
// Delete button
// ---------------------------------------------------------------------------

function DeleteButton({ file, onDeleted }: { file: StoredFile; onDeleted: () => void }) {
  const { t } = useTranslation();

  const mutation = useMutation({
    mutationFn: () => deleteAdminFile(file.id),
    onSuccess: () => {
      toast.success(t("admin.files.deleted", { defaultValue: "File deleted" }));
      onDeleted();
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(err, t("admin.files.delete_error", { defaultValue: "Delete failed" })),
      ),
  });

  return (
    <Button
      variant="ghost"
      size="icon"
      className="text-destructive hover:text-destructive"
      onClick={() => mutation.mutate()}
      disabled={mutation.isPending}
      title="Delete"
    >
      <Trash2 className="size-4" />
    </Button>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function FilesPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const table = useTableState();

  const {
    data: response,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["admin", "files", table.queryString],
    queryFn: () => getAdminFiles(table.queryString),
    placeholderData: (prev) => prev,
  });

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ["admin", "files"] });
  }

  const columns: Column<StoredFile>[] = [
    {
      key: "id",
      header: "ID",
      sortable: false,
      cell: (f) => <IdCell id={f.id} />,
      className: "w-32",
    },
    {
      key: "name",
      header: t("admin.files.col_name", { defaultValue: "Name" }),
      cell: (f) => <span className="font-medium">{f.name}</span>,
    },
    {
      key: "original_filename",
      header: t("admin.files.col_filename", { defaultValue: "Filename" }),
      cell: (f) => (
        <span className="text-muted-foreground text-xs font-mono">{f.original_filename}</span>
      ),
    },
    {
      key: "mime_type",
      header: t("admin.files.col_type", { defaultValue: "Type" }),
      cell: (f) => <span className="text-muted-foreground text-xs">{f.mime_type ?? "—"}</span>,
    },
    {
      key: "file_size",
      header: t("admin.files.col_size", { defaultValue: "Size" }),
      cell: (f) => (
        <span className="text-muted-foreground text-xs">{formatBytes(f.file_size)}</span>
      ),
    },
    {
      key: "is_public",
      header: t("admin.files.col_public", { defaultValue: "Public" }),
      sortable: false,
      cell: (f) => <PublicToggle file={f} onUpdated={invalidate} />,
      className: "w-16 text-center",
    },
    {
      key: "actions" as keyof StoredFile,
      header: "",
      sortable: false,
      cell: (f) => (
        <div className="flex items-center justify-end gap-1">
          <PreviewButton file={f} />
          <EditFileDialog file={f} onUpdated={invalidate} />
          <DeleteButton file={f} onDeleted={invalidate} />
        </div>
      ),
      className: "w-32 text-right",
    },
  ];

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("admin.nav.files", { defaultValue: "Files" })}</h1>
        <UploadFileDialog onCreated={invalidate} />
      </div>

      <DataTable
        columns={columns}
        response={response}
        table={table}
        isLoading={isLoading}
        isFetching={isFetching}
        rowKey={(f) => f.id}
        onRefresh={() => void refetch()}
      />
    </div>
  );
}
