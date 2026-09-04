import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Flag, Plus, Puzzle } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { type Column, DataTable, useTableState } from "@/components/data-table";
import { LabelInput } from "@/components/label-input";
import { PageHeader } from "@/components/page-header";
import { initFromSchema, SchemaFields } from "@/components/schema-form";
import { BoolCell, EmptyCell, idColumn, StatusCell } from "@/components/table-cells";
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

export const Route = createFileRoute("/admin/_admin/challenges")({
  component: ChallengesPage,
});

// ── Columns & filters ────────────────────────────────────────────────────────

// ── Schema field renderer (for extra plugin-specific fields) ─────────────────

export const BASE_CHALLENGE_FIELDS = [
  "title",
  "description",
  "writeup",
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
  writeup: "",
  is_active: false,
  sequential: false,
  category: null as string | null,
  tags: [] as string[],
};

function CreateChallengeDialog({ onCreated }: { onCreated: (id: string) => void }) {
  const { t } = useTranslation();
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
      toast.success(t("admin.challenges.created", { defaultValue: "Challenge created" }));
      handleClose();
      onCreated(challenge.id);
    },
    onError: (err) =>
      toast.error(
        apiErrorMessage(
          err,
          t("admin.challenges.create_error", { defaultValue: "Failed to create challenge" }),
        ),
      ),
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
    const typeInfo = types.find((ct) => ct.type_name === typeName)!;
    setSelectedType(typeName);
    setForm({ ...EMPTY_BASE, ...initExtras(typeInfo) });
    setStep(2);
  }

  const selectedSchema = types.find((ct) => ct.type_name === selectedType)?.create_schema;

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
            {t("admin.challenges.new", { defaultValue: "New Challenge" })}
          </Button>
        }
      />
      <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {step === 1
              ? t("admin.challenges.select_type", { defaultValue: "Select challenge type" })
              : t("admin.challenges.new_typed_title", {
                  defaultValue: "New {{type}} challenge",
                  type: selectedType,
                })}
          </DialogTitle>
        </DialogHeader>

        {step === 1 ? (
          <div className="grid grid-cols-2 gap-3 mt-2">
            {types.length === 0 && (
              <p className="col-span-2 text-center text-sm text-muted-foreground py-8">
                {t("admin.challenges.no_types", {
                  defaultValue: "No challenge types registered",
                })}
              </p>
            )}
            {types.map((ct) => (
              <button
                key={ct.type_name}
                type="button"
                onClick={() => handleTypeSelect(ct.type_name)}
                className="flex flex-col items-start gap-1 rounded-lg border p-4 text-left hover:border-primary hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Puzzle className="size-4 text-muted-foreground" />
                  <span className="font-medium capitalize">{ct.type_name}</span>
                </div>
                <span className="text-xs text-muted-foreground">
                  {t("admin.challenges.type_hint", { defaultValue: "Challenge type" })}
                </span>
              </button>
            ))}
          </div>
        ) : selectedSchema ? (
          <form onSubmit={handleSubmit} className="space-y-4 mt-2">
            <div className="space-y-1.5">
              <Label htmlFor="ch-title">{t("admin.challenge.field_title")} *</Label>
              <Input
                id="ch-title"
                value={String(form.title ?? "")}
                onChange={(e) => update({ title: e.target.value })}
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="ch-desc">{t("admin.challenge.field_description")}</Label>
              <MarkdownEditor
                id="ch-desc"
                rows={4}
                value={String(form.description ?? "")}
                onChange={(v) => update({ description: v || null })}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="ch-writeup">{t("admin.challenge.field_writeup")}</Label>
              <p className="text-xs text-muted-foreground">
                {t("admin.challenge.field_writeup_hint")}
              </p>
              <MarkdownEditor
                id="ch-writeup"
                rows={6}
                value={String(form.writeup ?? "")}
                onChange={(v) => update({ writeup: v || null })}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="ch-category">{t("admin.challenge.field_category")}</Label>
              <LabelInput
                id="ch-category"
                placeholder={t("admin.challenge.no_category")}
                noun="category"
                suggestions={categories}
                value={String(form.category ?? "")}
                onValueChange={(v) => update({ category: v || null })}
              />
            </div>

            <div className="space-y-1.5">
              <Label>{t("admin.challenge.field_tags")}</Label>
              <TagMultiSelect
                value={(form.tags as string[]) ?? []}
                onChange={(tags) => update({ tags })}
                suggestions={tagSuggestions}
              />
            </div>

            <div className="flex gap-3">
              <div className="flex flex-1 items-center justify-between rounded-lg border px-3 py-2.5">
                <div>
                  <p className="text-sm font-medium">{t("admin.challenge.active_label")}</p>
                  <p className="text-xs text-muted-foreground">
                    {t("admin.challenge.active_hint")}
                  </p>
                </div>
                <Switch
                  checked={Boolean(form.is_active)}
                  onCheckedChange={(v) => update({ is_active: v })}
                />
              </div>
              <div className="flex flex-1 items-center justify-between rounded-lg border px-3 py-2.5">
                <div>
                  <p className="text-sm font-medium">{t("admin.challenge.sequential_label")}</p>
                  <p className="text-xs text-muted-foreground">
                    {t("admin.challenge.sequential_hint")}
                  </p>
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
                {t("common.back")}
              </Button>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? t("common.creating") : t("common.create")}
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

  const { t } = useTranslation();
  const table = useTableState();
  const columns: Column<Challenge>[] = [
    idColumn<Challenge>(t),
    {
      key: "title",
      header: t("table.col_title", { defaultValue: "Title" }),
      cell: (c) => <span className="font-medium">{c.title}</span>,
    },
    {
      key: "challenge_type",
      header: t("table.col_type", { defaultValue: "Type" }),
      cell: (c) => (
        <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
          <Puzzle className="size-3" />
          {c.challenge_type}
        </span>
      ),
    },
    {
      key: "category",
      header: t("table.col_category", { defaultValue: "Category" }),
      cell: (c) =>
        c.category ? (
          <span className="text-muted-foreground capitalize">{c.category}</span>
        ) : (
          <EmptyCell />
        ),
    },
    {
      key: "is_active",
      header: t("table.col_status", { defaultValue: "Status" }),
      cell: (c) => <StatusCell active={c.is_active} />,
    },
    {
      key: "sequential",
      header: t("admin.challenges.col_sequential", { defaultValue: "Sequential" }),
      cell: (c) => <BoolCell value={c.sequential} />,
    },
    {
      key: "question_count",
      header: t("admin.challenges.col_questions", { defaultValue: "Questions" }),
      cell: (c) => <span className="text-muted-foreground">{c.question_count}</span>,
    },
  ];

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
      <PageHeader
        icon={Flag}
        title={t("admin.nav.challenges", { defaultValue: "Challenges" })}
        actions={<CreateChallengeDialog onCreated={handleCreated} />}
      />

      <DataTable
        columns={columns}
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
