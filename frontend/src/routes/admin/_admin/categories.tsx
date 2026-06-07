import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
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
import {
  apiErrorMessage,
  type Category,
  createCategory,
  deleteCategory,
  getAdminCategories,
  updateCategory,
} from "@/lib/api";

export const Route = createFileRoute("/admin/_admin/categories")({
  component: CategoriesPage,
});

// ── Columns ───────────────────────────────────────────────────────────────────

const COLUMNS: Column<Category>[] = [
  {
    key: "id",
    header: "ID",
    sortable: false,
    cell: (c) => <IdCell id={c.id} />,
    className: "w-32",
  },
  {
    key: "name",
    header: "Name",
    cell: (c) => <span className="font-medium">{c.name}</span>,
  },
  {
    key: "slug",
    header: "Slug",
    cell: (c) => <span className="font-mono text-xs text-muted-foreground">{c.slug}</span>,
  },
];

// ── Form fields ───────────────────────────────────────────────────────────────

function CategoryFormFields({
  form,
  onChange,
}: {
  form: { name: string; slug: string };
  onChange: (patch: Partial<typeof form>) => void;
}) {
  function autoSlug(name: string) {
    return name
      .toLowerCase()
      .trim()
      .replace(/\s+/g, "-")
      .replace(/[^a-z0-9-]/g, "");
  }

  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label>Name *</Label>
        <Input
          value={form.name}
          onChange={(e) => {
            const name = e.target.value;
            onChange({ name, slug: autoSlug(name) });
          }}
          required
        />
      </div>
      <div className="space-y-1.5">
        <Label>Slug *</Label>
        <Input
          value={form.slug}
          onChange={(e) => onChange({ slug: e.target.value })}
          className="font-mono"
          required
        />
      </div>
    </div>
  );
}

// ── Create dialog ─────────────────────────────────────────────────────────────

function CreateCategoryDialog({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", slug: "" });

  const mutation = useMutation({
    mutationFn: () => createCategory(form),
    onSuccess: () => {
      toast.success("Category created");
      setOpen(false);
      setForm({ name: "", slug: "" });
      onCreated();
    },
    onError: (err) => toast.error(apiErrorMessage(err, "Failed to create category")),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button>
            <Plus className="size-4" />
            New Category
          </Button>
        }
      />
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>New category</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
          className="space-y-4 mt-2"
        >
          <CategoryFormFields form={form} onChange={(p) => setForm((f) => ({ ...f, ...p }))} />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Creating…" : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ── Edit dialog ───────────────────────────────────────────────────────────────

function EditCategoryDialog({ category, onSaved }: { category: Category; onSaved: () => void }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    name: category.name,
    slug: category.slug,
  });

  const mutation = useMutation({
    mutationFn: () => updateCategory(category.id, form),
    onSuccess: () => {
      toast.success("Category saved");
      setOpen(false);
      onSaved();
    },
    onError: (err) => toast.error(apiErrorMessage(err, "Failed to save category")),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button variant="ghost" size="icon" className="size-7">
            <Pencil className="size-3.5" />
          </Button>
        }
      />
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Edit category</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
          className="space-y-4 mt-2"
        >
          <CategoryFormFields form={form} onChange={(p) => setForm((f) => ({ ...f, ...p }))} />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function CategoriesPage() {
  const queryClient = useQueryClient();

  const table = useTableState();

  const {
    data: response,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["admin", "categories", table.queryString],
    queryFn: () => getAdminCategories(table.queryString),
    placeholderData: (prev) => prev,
  });

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ["admin", "categories"] });
  }

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteCategory(id),
    onSuccess: () => {
      toast.success("Category deleted");
      invalidate();
    },
    onError: (err) => toast.error(apiErrorMessage(err, "Failed to delete category")),
  });

  const columnsWithActions: Column<Category>[] = [
    ...COLUMNS,
    {
      key: "_actions",
      header: "",
      sortable: false,
      className: "w-20",
      cell: (category) => (
        <div className="flex gap-1 justify-end">
          <EditCategoryDialog category={category} onSaved={invalidate} />
          <Button
            variant="ghost"
            size="icon"
            className="size-7 text-destructive hover:text-destructive"
            disabled={deleteMutation.isPending}
            onClick={(e) => {
              e.stopPropagation();
              if (confirm(`Delete category "${category.name}"?`)) {
                deleteMutation.mutate(category.id);
              }
            }}
          >
            <Trash2 className="size-3.5" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Categories</h1>
        <CreateCategoryDialog onCreated={invalidate} />
      </div>

      <DataTable
        columns={columnsWithActions}
        response={response}
        table={table}
        isLoading={isLoading}
        isFetching={isFetching}
        rowKey={(c) => c.id}
        onRefresh={() => void refetch()}
      />
    </div>
  );
}
