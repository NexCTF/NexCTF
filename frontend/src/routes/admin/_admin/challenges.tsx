import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Plus, Puzzle } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { type Column, DataTable, useTableState } from "@/components/data-table";
import { IdCell } from "@/components/id-cell";
import { LabelInput } from "@/components/label-input";
import { initFromSchema, SchemaFields } from "@/components/schema-form";
import { TagMultiSelect } from "@/components/tag-multi-select";
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
import { MarkdownEditor } from "@/components/ui/markdown-editor";
import { Switch } from "@/components/ui/switch";
import {
  apiErrorMessage,
  type Challenge,
  type ChallengeTypeInfo,
  createChallenge,
  getAdminChallenges,
  getChallengeTypes,
} from "@/lib/api";
import { useFacetValues, useTagSuggestions } from "@/lib/use-facet-values";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/admin/_admin/challenges")({
  component: ChallengesPage,
});

// ── Columns & filters ────────────────────────────────────────────────────────

const COLUMNS: Column<Challenge>[] = [
  {
    key: "id",
    header: "ID",
    sortable: false,
    cell: (c) => <IdCell id={c.id} />,
    className: "w-32",
  },
  {
    key: "title",
    header: "Title",
    cell: (c) => <span className="font-medium">{c.title}</span>,
  },
  {
    key: "challenge_type",
    header: "Type",
    cell: (c) => (
      <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
        <Puzzle className="size-3" />
        {c.challenge_type}
      </span>
    ),
  },
  {
    key: "category",
    header: "Category",
    cell: (c) => <span className="text-muted-foreground capitalize">{c.category ?? "—"}</span>,
  },
  {
    key: "is_active",
    header: "Status",
    cell: (c) => (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 text-xs",
          c.is_active ? "text-green-600 dark:text-green-400" : "text-muted-foreground",
        )}
      >
        <span
          className={cn(
            "size-1.5 rounded-full",
            c.is_active ? "bg-green-500" : "bg-muted-foreground/50",
          )}
        />
        {c.is_active ? "Active" : "Inactive"}
      </span>
    ),
  },
  {
    key: "sequential",
    header: "Sequential",
    cell: (c) => <span className="text-muted-foreground">{c.sequential ? "Yes" : "No"}</span>,
  },
  {
    key: "question_count",
    header: "Questions",
    cell: (c) => <span className="text-muted-foreground">{c.question_count}</span>,
  },
];

// ── Schema field renderer (for extra plugin-specific fields) ─────────────────

const BASE_CHALLENGE_FIELDS = [
  "title",
  "description",
  "is_active",
  "sequential",
  "category",
  "tags",
  "author_id",
  "id",
];

// ── Create dialog ─────────────────────────────────────────────────────────────

type CreateStep = 1 | 2;

const EMPTY_BASE = {
  title: "",
  description: "",
  is_active: false,
  sequential: false,
  category: null as string | null,
  tags: [] as string[],
};

function CreateChallengeDialog({ onCreated }: { onCreated: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<CreateStep>(1);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [form, setForm] = useState<Record<string, unknown>>({ ...EMPTY_BASE });

  const { data: types = [] } = useQuery({
    queryKey: ["admin", "challenge-types"],
    queryFn: getChallengeTypes,
    staleTime: Infinity,
  });

  const categories = useFacetValues("/admin/challenge", "category");
  const tagSuggestions = useTagSuggestions();

  const mutation = useMutation({
    mutationFn: ({ type, data }: { type: string; data: Record<string, unknown> }) =>
      createChallenge(type, data),
    onSuccess: (challenge) => {
      toast.success("Challenge created");
      handleClose();
      onCreated(challenge.id);
    },
    onError: (err) => toast.error(apiErrorMessage(err, "Failed to create challenge")),
  });

  function handleClose() {
    setOpen(false);
    setStep(1);
    setSelectedType(null);
    setForm({ ...EMPTY_BASE });
  }

  function initExtras(typeInfo: ChallengeTypeInfo) {
    return initFromSchema(typeInfo.create_schema, new Set(BASE_CHALLENGE_FIELDS));
  }

  function handleTypeSelect(typeName: string) {
    // biome-ignore lint/style/noNonNullAssertion: typeName comes from types selection UI
    const typeInfo = types.find((t) => t.type_name === typeName)!;
    setSelectedType(typeName);
    setForm({ ...EMPTY_BASE, ...initExtras(typeInfo) });
    setStep(2);
  }

  const selectedSchema = types.find((t) => t.type_name === selectedType)?.create_schema;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedType) return;
    mutation.mutate({ type: selectedType, data: form });
  }

  function update(patch: Record<string, unknown>) {
    setForm((f) => ({ ...f, ...patch }));
  }

  return (
    <Dialog open={open} onOpenChange={(v) => (v ? setOpen(true) : handleClose())}>
      <DialogTrigger
        render={
          <Button>
            <Plus className="size-4" />
            New Challenge
          </Button>
        }
      />
      <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {step === 1 ? "Select challenge type" : `New ${selectedType} challenge`}
          </DialogTitle>
        </DialogHeader>

        {step === 1 ? (
          <div className="grid grid-cols-2 gap-3 mt-2">
            {types.length === 0 && (
              <p className="col-span-2 text-center text-sm text-muted-foreground py-8">
                No challenge types registered
              </p>
            )}
            {types.map((t) => (
              <button
                key={t.type_name}
                type="button"
                onClick={() => handleTypeSelect(t.type_name)}
                className="flex flex-col items-start gap-1 rounded-lg border p-4 text-left hover:border-primary hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Puzzle className="size-4 text-muted-foreground" />
                  <span className="font-medium capitalize">{t.type_name}</span>
                </div>
                <span className="text-xs text-muted-foreground">Challenge type</span>
              </button>
            ))}
          </div>
        ) : selectedSchema ? (
          <form onSubmit={handleSubmit} className="space-y-4 mt-2">
            <div className="space-y-1.5">
              <Label htmlFor="ch-title">Title *</Label>
              <Input
                id="ch-title"
                value={String(form.title ?? "")}
                onChange={(e) => update({ title: e.target.value })}
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="ch-desc">Description</Label>
              <MarkdownEditor
                id="ch-desc"
                rows={4}
                value={String(form.description ?? "")}
                onChange={(v) => update({ description: v || null })}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="ch-category">Category</Label>
              <LabelInput
                id="ch-category"
                placeholder="No category"
                noun="category"
                suggestions={categories}
                value={String(form.category ?? "")}
                onValueChange={(v) => update({ category: v || null })}
              />
            </div>

            <div className="space-y-1.5">
              <Label>Tags</Label>
              <TagMultiSelect
                value={(form.tags as string[]) ?? []}
                onChange={(tags) => update({ tags })}
                suggestions={tagSuggestions}
              />
            </div>

            <div className="flex gap-3">
              <div className="flex flex-1 items-center justify-between rounded-lg border px-3 py-2.5">
                <div>
                  <p className="text-sm font-medium">Active</p>
                  <p className="text-xs text-muted-foreground">Visible to players</p>
                </div>
                <Switch
                  checked={Boolean(form.is_active)}
                  onCheckedChange={(v) => update({ is_active: v })}
                />
              </div>
              <div className="flex flex-1 items-center justify-between rounded-lg border px-3 py-2.5">
                <div>
                  <p className="text-sm font-medium">Sequential</p>
                  <p className="text-xs text-muted-foreground">Ordered questions</p>
                </div>
                <Switch
                  checked={Boolean(form.sequential)}
                  onCheckedChange={(v) => update({ sequential: v })}
                />
              </div>
            </div>

            <SchemaFields
              schema={selectedSchema}
              skip={BASE_CHALLENGE_FIELDS}
              values={form}
              onChange={(key, val) => update({ [key]: val })}
            />

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setStep(1)}>
                Back
              </Button>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? "Creating…" : "Create"}
              </Button>
            </DialogFooter>
          </form>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

function ChallengesPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const table = useTableState();

  const {
    data: response,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["admin", "challenges", table.queryString],
    queryFn: () => getAdminChallenges(table.queryString),
    placeholderData: (prev) => prev,
  });

  function handleCreated(id: string) {
    void queryClient.invalidateQueries({ queryKey: ["admin", "challenges"] });
    void navigate({
      to: "/admin/challenges/$challengeId",
      params: { challengeId: id },
    });
  }

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Challenges</h1>
        <CreateChallengeDialog onCreated={handleCreated} />
      </div>

      <DataTable
        columns={COLUMNS}
        response={response}
        table={table}
        isLoading={isLoading}
        isFetching={isFetching}
        rowKey={(c) => c.id}
        onRefresh={() => void refetch()}
        onRowClick={(c) =>
          void navigate({
            to: "/admin/challenges/$challengeId",
            params: { challengeId: c.id },
          })
        }
      />
    </div>
  );
}
