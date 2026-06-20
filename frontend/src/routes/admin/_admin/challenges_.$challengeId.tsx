import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import {
  ArrowDown,
  ArrowUp,
  ChevronDown,
  ChevronUp,
  Paperclip,
  Pencil,
  Plus,
  Puzzle,
  Trash2,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { DetailPageShell, DetailSection } from "@/components/detail-page";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
  apiErrorMessage,
  type ChallengeDetail,
  createHint,
  createQuestion,
  createSolution,
  deleteChallenge,
  deleteHint,
  deleteQuestion,
  deleteSolution,
  getAdminCategories,
  getAdminChallenge,
  getAdminFiles,
  getAdminHint,
  getAdminHints,
  getAdminQuestions,
  getAdminSolution,
  getAdminSolutions,
  getChallengeTypes,
  getSolutionTypes,
  type Hint,
  type InputType,
  type Question,
  type Solution,
  type SolutionTypeInfo,
  updateChallenge,
  updateHint,
  updateQuestion,
  updateSolution,
} from "@/lib/api";
export const Route = createFileRoute("/admin/_admin/challenges_/$challengeId")({
  component: ChallengePage,
});

// ── Schema helpers ────────────────────────────────────────────────────────────

const NO_CATEGORY = "__none__";
const SKIP_SOL = new Set(["id", "question_id"]);

const SKIP_CHALLENGE = new Set([
  "id",
  "title",
  "description",
  "is_active",
  "sequential",
  "category_id",
  "author_id",
  "tags_ids",
]);

// ── Challenge info section ─────────────────────────────────────────────────────

function ChallengeInfoSection({ challenge }: { challenge: ChallengeDetail }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const { data: types = [] } = useQuery({
    queryKey: ["admin", "challenge-types"],
    queryFn: getChallengeTypes,
    staleTime: Infinity,
  });

  const { data: categoriesResp } = useQuery({
    queryKey: ["admin", "categories", "all"],
    queryFn: () => getAdminCategories("items_per_page=100"),
    staleTime: 30_000,
  });
  const categories = categoriesResp?.data ?? [];

  const typeInfo = types.find((t) => t.type_name === challenge.challenge_type);
  const updateSchema = typeInfo?.update_schema ?? { properties: {} };

  // Track whether the initial form was seeded with a valid schema (warm cache).
  // If types weren't loaded yet at mount time, the effect below fills the gap.
  const schemaSeedRef = useRef(!!typeInfo);

  const [form, setForm] = useState<Record<string, unknown>>(() => ({
    title: challenge.title,
    description: challenge.description,
    is_active: challenge.is_active,
    sequential: challenge.sequential,
    category_id: challenge.category_id,
    tags_ids: (challenge.tags ?? []).map((t) => t.id),
    ...initFromSchema(
      updateSchema,
      SKIP_CHALLENGE,
      challenge as unknown as Record<string, unknown>,
    ),
  }));

  // When the types query resolves after mount (cold cache), merge plugin-specific
  // fields into the form. Skipped on warm cache since useState already seeded them.
  // biome-ignore lint/correctness/useExhaustiveDependencies: challenge and SKIP_CHALLENGE are stable for page lifetime
  useEffect(() => {
    if (!typeInfo || schemaSeedRef.current) return;
    schemaSeedRef.current = true;
    const extras = initFromSchema(
      typeInfo.update_schema,
      SKIP_CHALLENGE,
      challenge as unknown as Record<string, unknown>,
    );
    setForm((f) => ({ ...extras, ...f }));
  }, [typeInfo?.type_name]);

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => updateChallenge(challenge.id, data),
    onSuccess: () => {
      toast.success(t("admin.challenge.saved"));
      void queryClient.invalidateQueries({
        queryKey: ["admin", "challenge", challenge.id],
      });
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.challenge.save_error"))),
  });

  function update(patch: Record<string, unknown>) {
    setForm((f) => ({ ...f, ...patch }));
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        mutation.mutate(form);
      }}
      className="rounded-lg border p-6 space-y-4"
    >
      <h2 className="text-base font-semibold">{t("admin.challenge.info_title")}</h2>

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
          rows={5}
          value={String(form.description ?? "")}
          onChange={(v) => update({ description: v || null })}
        />
      </div>

      <div className="space-y-1.5">
        <Label>{t("admin.challenge.field_category")}</Label>
        <Select
          value={String(form.category_id ?? NO_CATEGORY)}
          onValueChange={(v) => update({ category_id: v === NO_CATEGORY ? null : v })}
        >
          <SelectTrigger>
            <SelectValue>
              {categories.find((c) => c.id === form.category_id)?.name ??
                t("admin.challenge.no_category")}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={NO_CATEGORY}>{t("admin.challenge.no_category")}</SelectItem>
            {categories.map((c) => (
              <SelectItem key={c.id} value={c.id}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex gap-3">
        <div className="flex flex-1 items-center justify-between rounded-lg border px-3 py-2.5">
          <div>
            <p className="text-sm font-medium">{t("admin.challenge.active_label")}</p>
            <p className="text-xs text-muted-foreground">{t("admin.challenge.active_hint")}</p>
          </div>
          <Switch
            checked={Boolean(form.is_active)}
            onCheckedChange={(v) => update({ is_active: v })}
          />
        </div>
        <div className="flex flex-1 items-center justify-between rounded-lg border px-3 py-2.5">
          <div>
            <p className="text-sm font-medium">{t("admin.challenge.sequential_label")}</p>
            <p className="text-xs text-muted-foreground">{t("admin.challenge.sequential_hint")}</p>
          </div>
          <Switch
            checked={Boolean(form.sequential)}
            onCheckedChange={(v) => update({ sequential: v })}
          />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label>{t("admin.challenge.field_tags")}</Label>
        <TagMultiSelect
          value={(form.tags_ids as string[]) ?? []}
          onChange={(ids) => update({ tags_ids: ids })}
        />
      </div>

      {/* Plugin-specific extra fields */}
      <SchemaFields
        schema={updateSchema}
        skip={SKIP_CHALLENGE}
        values={form}
        defs={updateSchema.$defs}
        onChange={(key, val) => update({ [key]: val })}
      />

      <div className="flex justify-end pt-2">
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? t("common.saving") : t("admin.challenge.save_changes")}
        </Button>
      </div>
    </form>
  );
}

// ── Add/Edit question dialogs ─────────────────────────────────���──────────────

const INPUT_TYPES: InputType[] = ["input", "text", "code", "mcq"];

function QuestionFormFields({
  form,
  onUpdate,
}: {
  form: Record<string, unknown>;
  onUpdate: (patch: Record<string, unknown>) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label>{t("admin.challenge.question.field_label")} *</Label>
        <Input
          value={String(form.label ?? "")}
          onChange={(e) => onUpdate({ label: e.target.value })}
          required
        />
      </div>
      <div className="space-y-1.5">
        <Label>{t("admin.challenge.question.field_description")}</Label>
        <MarkdownEditor
          rows={3}
          value={String(form.description ?? "")}
          onChange={(v) => onUpdate({ description: v || null })}
        />
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div className="space-y-1.5">
          <Label>{t("admin.challenge.question.field_points")}</Label>
          <Input
            type="number"
            value={String(form.points ?? 100)}
            onChange={(e) => onUpdate({ points: Number(e.target.value) })}
          />
        </div>
        <div className="space-y-1.5">
          <Label>{t("admin.challenge.question.field_malus")}</Label>
          <Input
            type="number"
            value={form.malus === null || form.malus === undefined ? "" : String(form.malus)}
            placeholder={t("admin.challenge.question.field_malus_placeholder")}
            onChange={(e) =>
              onUpdate({
                malus: e.target.value === "" ? null : Number(e.target.value),
              })
            }
          />
        </div>
        <div className="space-y-1.5">
          <Label>{t("admin.challenge.question.field_input_type")}</Label>
          <Select
            value={String(form.input_type ?? "input")}
            onValueChange={(v) => onUpdate({ input_type: v })}
          >
            <SelectTrigger>
              <SelectValue>
                {t(`admin.challenge.question.input_type_${String(form.input_type ?? "input")}`)}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              {INPUT_TYPES.map((type) => (
                <SelectItem key={type} value={type}>
                  {t(`admin.challenge.question.input_type_${type}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
    </div>
  );
}

function AddQuestionDialog({
  challengeId,
  questionCount,
  onCreated,
}: {
  challengeId: string;
  questionCount: number;
  onCreated: () => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<Record<string, unknown>>({
    label: "",
    description: null,
    points: 100,
    malus: null,
    input_type: "input",
  });

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      createQuestion({
        ...data,
        challenge_id: challengeId,
        index: questionCount,
      }),
    onSuccess: () => {
      toast.success(t("admin.challenge.question.added"));
      setOpen(false);
      setForm({
        label: "",
        description: null,
        points: 100,
        malus: null,
        input_type: "input",
      });
      onCreated();
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.challenge.question.add_error"))),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button variant="outline" size="sm">
            <Plus className="size-3.5" />
            {t("admin.challenge.question.add")}
          </Button>
        }
      />
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t("admin.challenge.question.new_title")}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate(form);
          }}
          className="space-y-4 mt-2"
        >
          <QuestionFormFields
            form={form}
            onUpdate={(patch) => setForm((f) => ({ ...f, ...patch }))}
          />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? t("common.adding") : t("common.add")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function EditQuestionDialog({ question, onSaved }: { question: Question; onSaved: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<Record<string, unknown>>({
    label: question.label,
    description: question.description ?? null,
    points: question.points,
    malus: question.malus,
    index: question.index,
    input_type: question.input_type ?? "input",
    tags_ids: (question.tags ?? []).map((t) => t.id),
  });

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => updateQuestion(question.id, data),
    onSuccess: () => {
      toast.success(t("admin.challenge.question.saved"));
      setOpen(false);
      onSaved();
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.challenge.question.save_error"))),
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
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t("admin.challenge.question.edit_title")}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate(form);
          }}
          className="space-y-4 mt-2"
        >
          <QuestionFormFields
            form={form}
            onUpdate={(patch) => setForm((f) => ({ ...f, ...patch }))}
          />
          <div className="space-y-1.5">
            <Label>{t("admin.challenge.question.field_tags")}</Label>
            <TagMultiSelect
              value={(form.tags_ids as string[]) ?? []}
              onChange={(ids) => setForm((f) => ({ ...f, tags_ids: ids }))}
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? t("common.saving") : t("common.save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ── Solutions section ─────────────────────────────────────────────────────���───

function AddSolutionDialog({
  questionId,
  solutionTypes,
  onCreated,
}: {
  questionId: string;
  solutionTypes: SolutionTypeInfo[];
  onCreated: () => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<1 | 2>(1);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [form, setForm] = useState<Record<string, unknown>>({});

  const mutation = useMutation({
    mutationFn: ({ type, data }: { type: string; data: Record<string, unknown> }) =>
      createSolution(type, { ...data, question_id: questionId }),
    onSuccess: () => {
      toast.success(t("admin.challenge.solution.added"));
      handleClose();
      onCreated();
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.challenge.solution.add_error"))),
  });

  function handleClose() {
    setOpen(false);
    setStep(1);
    setSelectedType(null);
    setForm({});
  }

  function handleTypeSelect(typeName: string) {
    // biome-ignore lint/style/noNonNullAssertion: typeName comes from solutionTypes selection UI
    const typeInfo = solutionTypes.find((t) => t.type_name === typeName)!;
    setSelectedType(typeName);
    setForm(initFromSchema(typeInfo.create_schema, SKIP_SOL));
    setStep(2);
  }

  const schema = solutionTypes.find((t) => t.type_name === selectedType)?.create_schema;

  return (
    <Dialog open={open} onOpenChange={(v) => (v ? setOpen(true) : handleClose())}>
      <DialogTrigger
        render={
          <Button variant="outline" size="sm" className="h-7 text-xs">
            <Plus className="size-3" />
            {t("admin.challenge.solution.add")}
          </Button>
        }
      />
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {step === 1
              ? t("admin.challenge.solution.select_type")
              : t("admin.challenge.solution.new_title", { type: selectedType })}
          </DialogTitle>
        </DialogHeader>
        {step === 1 ? (
          <div className="grid grid-cols-2 gap-3 mt-2">
            {solutionTypes.map((t) => (
              <button
                key={t.type_name}
                type="button"
                onClick={() => handleTypeSelect(t.type_name)}
                className="flex flex-col gap-1 rounded-lg border p-3 text-left hover:border-primary hover:bg-muted/50 transition-colors"
              >
                <span className="font-medium capitalize">{t.type_name}</span>
                {t.description && (
                  <span className="text-xs text-muted-foreground leading-snug">
                    {t.description}
                  </span>
                )}
              </button>
            ))}
          </div>
        ) : schema ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!selectedType) return;
              mutation.mutate({ type: selectedType, data: form });
            }}
            className="space-y-4 mt-2"
          >
            <SchemaFields
              schema={schema}
              skip={SKIP_SOL}
              values={form}
              defs={schema.$defs}
              onChange={(key, val) => setForm((f) => ({ ...f, [key]: val }))}
            />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setStep(1)}>
                {t("common.back")}
              </Button>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? t("common.adding") : t("common.add")}
              </Button>
            </DialogFooter>
          </form>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function EditSolutionDialog({
  solution,
  solutionTypes,
  onSaved,
}: {
  solution: Solution;
  solutionTypes: SolutionTypeInfo[];
  onSaved: () => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  const typeInfo = solutionTypes.find((t) => t.type_name === solution.solve_type);
  const schema = typeInfo?.update_schema ?? { properties: {} };

  // Fetch full solution data when dialog opens; user edits override it
  const { data: fullSolution } = useQuery({
    queryKey: ["admin", "solution", solution.id],
    queryFn: () => getAdminSolution(solution.id),
    enabled: open,
  });

  const [overrides, setOverrides] = useState<Record<string, unknown>>({});

  // Derive form: base from fetched data, overridden by user edits
  const form = fullSolution
    ? { ...initFromSchema(schema, SKIP_SOL, fullSolution), ...overrides }
    : overrides;

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => updateSolution(solution.id, data),
    onSuccess: () => {
      toast.success(t("admin.challenge.solution.saved"));
      setOpen(false);
      setOverrides({});
      onSaved();
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.challenge.solution.save_error"))),
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (!v) setOverrides({});
      }}
    >
      <DialogTrigger
        render={
          <Button variant="ghost" size="icon" className="size-6">
            <Pencil className="size-3" />
          </Button>
        }
      />
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {t("admin.challenge.solution.edit_title", {
              type: solution.solve_type,
            })}
          </DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate(form);
          }}
          className="space-y-4 mt-2"
        >
          {!fullSolution ? (
            <div className="py-4 text-center text-sm text-muted-foreground">
              {t("common.loading")}
            </div>
          ) : (
            <SchemaFields
              schema={schema}
              skip={SKIP_SOL}
              values={form}
              defs={schema.$defs}
              onChange={(key, val) => setOverrides((o) => ({ ...o, [key]: val }))}
            />
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={mutation.isPending || !fullSolution}>
              {mutation.isPending ? t("common.saving") : t("common.save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ── Hint dialogs ──────────────────────────────────────────────────────────────

const EMPTY_HINT = { title: "", content: "", cost: 0, order: 0 };

function AddHintDialog({ questionId, onCreated }: { questionId: string; onCreated: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_HINT });

  const mutation = useMutation({
    mutationFn: () => createHint({ question_id: questionId, ...form }),
    onSuccess: () => {
      toast.success(t("admin.challenge.hint.added"));
      setOpen(false);
      setForm({ ...EMPTY_HINT });
      onCreated();
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.challenge.hint.add_error"))),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button variant="outline" size="sm" className="h-7 text-xs">
            <Plus className="size-3" />
            {t("admin.challenge.hint.add")}
          </Button>
        }
      />
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t("admin.challenge.hint.new_title")}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
          className="space-y-4 mt-2"
        >
          <div className="space-y-1.5">
            <Label>{t("admin.challenge.hint.field_title")} *</Label>
            <Input
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label>{t("admin.challenge.hint.field_content")} *</Label>
            <MarkdownEditor
              rows={3}
              value={form.content}
              onChange={(v) => setForm((f) => ({ ...f, content: v }))}
              required
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>{t("admin.challenge.hint.field_cost")}</Label>
              <Input
                type="number"
                value={form.cost}
                onChange={(e) => setForm((f) => ({ ...f, cost: Number(e.target.value) }))}
              />
            </div>
            <div className="space-y-1.5">
              <Label>{t("admin.challenge.hint.field_order")}</Label>
              <Input
                type="number"
                value={form.order}
                onChange={(e) => setForm((f) => ({ ...f, order: Number(e.target.value) }))}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? t("common.adding") : t("common.add")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function EditHintDialog({ hint, onSaved }: { hint: Hint; onSaved: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [overrides, setOverrides] = useState<Partial<typeof EMPTY_HINT>>({});

  // Fetch full hint content when dialog opens; user edits override it
  const { data: fullHint } = useQuery({
    queryKey: ["admin", "hint", hint.id],
    queryFn: () => getAdminHint(hint.id),
    enabled: open,
  });

  const base = fullHint
    ? {
        title: fullHint.title,
        content: fullHint.content ?? "",
        cost: fullHint.cost,
        order: fullHint.order,
      }
    : {
        title: hint.title,
        content: hint.content ?? "",
        cost: hint.cost,
        order: hint.order,
      };
  const form = { ...base, ...overrides };

  const mutation = useMutation({
    mutationFn: () => updateHint(hint.id, form),
    onSuccess: () => {
      toast.success(t("admin.challenge.hint.saved"));
      setOpen(false);
      setOverrides({});
      onSaved();
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.challenge.hint.save_error"))),
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (!v) setOverrides({});
      }}
    >
      <DialogTrigger
        render={
          <Button variant="ghost" size="icon" className="size-6">
            <Pencil className="size-3" />
          </Button>
        }
      />
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t("admin.challenge.hint.edit_title")}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
          className="space-y-4 mt-2"
        >
          <div className="space-y-1.5">
            <Label>{t("admin.challenge.hint.field_title")} *</Label>
            <Input
              value={form.title}
              onChange={(e) => setOverrides((o) => ({ ...o, title: e.target.value }))}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label>{t("admin.challenge.hint.field_content")} *</Label>
            <MarkdownEditor
              rows={3}
              value={form.content}
              onChange={(v) => setOverrides((o) => ({ ...o, content: v }))}
              required
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>{t("admin.challenge.hint.field_cost")}</Label>
              <Input
                type="number"
                value={form.cost}
                onChange={(e) => setOverrides((o) => ({ ...o, cost: Number(e.target.value) }))}
              />
            </div>
            <div className="space-y-1.5">
              <Label>{t("admin.challenge.hint.field_order")}</Label>
              <Input
                type="number"
                value={form.order}
                onChange={(e) => setOverrides((o) => ({ ...o, order: Number(e.target.value) }))}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? t("common.saving") : t("common.save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ── Files dialog ──────────────────────────────────────────────────────────────

function ManageFilesDialog({ question, onSaved }: { question: Question; onSaved: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(question.files.map((f) => f.id)),
  );

  const { data: filesResp, isLoading } = useQuery({
    queryKey: ["admin", "files", "all"],
    queryFn: () => getAdminFiles("items_per_page=200"),
    enabled: open,
    staleTime: 30_000,
  });
  const allFiles = filesResp?.data ?? [];

  const filtered = search.trim()
    ? allFiles.filter(
        (f) =>
          f.name.toLowerCase().includes(search.toLowerCase()) ||
          f.original_filename.toLowerCase().includes(search.toLowerCase()),
      )
    : allFiles;

  const mutation = useMutation({
    mutationFn: () => updateQuestion(question.id, { files_ids: [...selected] }),
    onSuccess: () => {
      toast.success(t("admin.challenge.file.updated"));
      setOpen(false);
      onSaved();
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.challenge.file.update_error"))),
  });

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (v) {
          setSelected(new Set(question.files.map((f) => f.id)));
          setSearch("");
        }
      }}
    >
      <DialogTrigger
        render={
          <Button variant="outline" size="sm" className="h-7 text-xs">
            <Paperclip className="size-3" />
            {t("admin.challenge.file.manage")}
          </Button>
        }
      />
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t("admin.challenge.file.attach_title")}</DialogTitle>
        </DialogHeader>

        {isLoading ? (
          <p className="py-4 text-center text-sm text-muted-foreground">{t("common.loading")}</p>
        ) : allFiles.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">
            {t("admin.challenge.file.no_files")}
          </p>
        ) : (
          <div className="space-y-2">
            <Input
              placeholder={t("admin.challenge.file.search_placeholder")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-8 text-sm"
            />
            <div className="max-h-64 overflow-y-auto space-y-1 border rounded-md p-2">
              {filtered.length === 0 ? (
                <p className="py-3 text-center text-sm text-muted-foreground">
                  {t("admin.challenge.file.no_match")}
                </p>
              ) : (
                filtered.map((file) => (
                  <label
                    key={file.id}
                    className="flex items-center gap-3 rounded px-2 py-1.5 hover:bg-muted/50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selected.has(file.id)}
                      onChange={() => toggle(file.id)}
                      className="rounded"
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{file.name}</p>
                      <p className="text-xs text-muted-foreground truncate">
                        {file.original_filename}
                        {file.mime_type && ` · ${file.mime_type}`}
                      </p>
                    </div>
                  </label>
                ))
              )}
            </div>
          </div>
        )}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => setOpen(false)}>
            {t("common.cancel")}
          </Button>
          <Button onClick={() => mutation.mutate()} disabled={mutation.isPending || isLoading}>
            {mutation.isPending
              ? t("common.saving")
              : t("admin.challenge.file.save_files", { count: selected.size })}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Question card ─────────────────────────────────────────────────────────────

function QuestionCard({
  question,
  solutionTypes,
  isFirst,
  isLast,
  onDeleted,
  onUpdated,
  onMoveUp,
  onMoveDown,
  onCountChanged,
}: {
  question: Question;
  solutionTypes: SolutionTypeInfo[];
  isFirst: boolean;
  isLast: boolean;
  onDeleted: (id: string) => void;
  onUpdated: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onCountChanged: () => void;
}) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);

  const solQS = `question_id=${question.id}&items_per_page=50`;
  const hintQS = `question_id=${question.id}&items_per_page=50&order_by=order&order=asc`;

  const { data: solutionsResp, refetch: refetchSolutions } = useQuery({
    queryKey: ["admin", "solutions", question.id],
    queryFn: () => getAdminSolutions(solQS),
    enabled: expanded,
  });

  const { data: hintsResp, refetch: refetchHints } = useQuery({
    queryKey: ["admin", "hints", question.id],
    queryFn: () => getAdminHints(hintQS),
    enabled: expanded,
  });

  const solutions = solutionsResp?.data ?? [];
  const hints = hintsResp?.data ?? [];

  const deleteMutation = useMutation({
    mutationFn: () => deleteQuestion(question.id),
    onSuccess: () => {
      toast.success(t("admin.challenge.question.deleted"));
      onDeleted(question.id);
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.challenge.question.delete_error"))),
  });

  const deleteSolutionMutation = useMutation({
    mutationFn: (id: string) => deleteSolution(id),
    onSuccess: () => {
      toast.success(t("admin.challenge.solution.deleted"));
      void refetchSolutions();
      onCountChanged();
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.challenge.solution.delete_error"))),
  });

  const deleteHintMutation = useMutation({
    mutationFn: (id: string) => deleteHint(id),
    onSuccess: () => {
      toast.success(t("admin.challenge.hint.deleted"));
      void refetchHints();
      onCountChanged();
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.challenge.hint.delete_error"))),
  });

  return (
    <div className="rounded-lg border">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3">
        <span className="text-xs text-muted-foreground w-6 text-center font-mono">
          #{question.index + 1}
        </span>
        <span className="flex-1 font-medium text-sm truncate">{question.label}</span>
        {question.input_type && question.input_type !== "input" && (
          <span className="text-xs rounded border px-1.5 py-0.5 text-muted-foreground shrink-0">
            {t(`admin.challenge.question.input_type_${question.input_type}`)}
          </span>
        )}
        <span className="text-xs text-muted-foreground shrink-0">
          {question.points} pts
          {question.malus !== null && <span className="text-destructive"> −{question.malus}</span>}
        </span>
        <span className="text-xs text-muted-foreground shrink-0">
          {question.solution_count} solution
          {question.solution_count !== 1 ? "s" : ""}
          {" · "}
          {question.hint_count} hint{question.hint_count !== 1 ? "s" : ""}
          {" · "}
          {question.file_count} file{question.file_count !== 1 ? "s" : ""}
        </span>
        <div className="flex items-center gap-1 shrink-0">
          <Button
            variant="ghost"
            size="icon"
            className="size-7"
            disabled={isFirst}
            onClick={onMoveUp}
          >
            <ArrowUp className="size-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="size-7"
            disabled={isLast}
            onClick={onMoveDown}
          >
            <ArrowDown className="size-3.5" />
          </Button>
          <EditQuestionDialog question={question} onSaved={onUpdated} />
          <Button
            variant="ghost"
            size="icon"
            className="size-7 text-destructive hover:text-destructive"
            onClick={() => {
              if (confirm(t("admin.challenge.question.delete_confirm"))) {
                deleteMutation.mutate();
              }
            }}
            disabled={deleteMutation.isPending}
          >
            <Trash2 className="size-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="size-7"
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
          </Button>
        </div>
      </div>

      {/* Expanded body */}
      {expanded && (
        <div className="border-t px-4 py-4 space-y-4">
          {/* Solutions */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                {t("admin.challenge.solution.section_title", {
                  count: solutions.length,
                })}
              </span>
              <AddSolutionDialog
                questionId={question.id}
                solutionTypes={solutionTypes.filter(
                  (t) =>
                    t.compatible_input_types === null ||
                    t.compatible_input_types.includes(
                      (question.input_type ?? "input") as InputType,
                    ),
                )}
                onCreated={() => {
                  void refetchSolutions();
                  onCountChanged();
                }}
              />
            </div>
            {solutions.length === 0 ? (
              <p className="text-xs text-muted-foreground py-1">
                {t("admin.challenge.solution.empty")}
              </p>
            ) : (
              <div className="space-y-1">
                {solutions.map((sol) => (
                  <div
                    key={sol.id}
                    className="flex items-center gap-2 rounded-md border px-3 py-1.5"
                  >
                    <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                      {sol.solve_type}
                    </span>
                    <span className="flex-1 text-xs text-muted-foreground">
                      {t("admin.challenge.solution.click_edit")}
                    </span>
                    <div className="flex items-center gap-1">
                      <EditSolutionDialog
                        solution={sol}
                        solutionTypes={solutionTypes}
                        onSaved={() => void refetchSolutions()}
                      />
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-6 text-destructive hover:text-destructive"
                        onClick={() => {
                          if (confirm(t("admin.challenge.solution.delete_confirm"))) {
                            deleteSolutionMutation.mutate(sol.id);
                          }
                        }}
                      >
                        <Trash2 className="size-3" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Hints */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                {t("admin.challenge.hint.section_title", {
                  count: hints.length,
                })}
              </span>
              <AddHintDialog
                questionId={question.id}
                onCreated={() => {
                  void refetchHints();
                  onCountChanged();
                }}
              />
            </div>
            {hints.length === 0 ? (
              <p className="text-xs text-muted-foreground py-1">
                {t("admin.challenge.hint.empty")}
              </p>
            ) : (
              <div className="space-y-1">
                {hints.map((hint) => (
                  <div
                    key={hint.id}
                    className="flex items-center gap-2 rounded-md border px-3 py-1.5"
                  >
                    <span className="flex-1 text-sm">{hint.title}</span>
                    <span className="text-xs text-muted-foreground">{hint.cost} pts</span>
                    <div className="flex items-center gap-1">
                      <EditHintDialog hint={hint} onSaved={() => void refetchHints()} />
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-6 text-destructive hover:text-destructive"
                        onClick={() => {
                          if (confirm(t("admin.challenge.hint.delete_confirm"))) {
                            deleteHintMutation.mutate(hint.id);
                          }
                        }}
                      >
                        <Trash2 className="size-3" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Files */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                {t("admin.challenge.file.section_title", {
                  count: question.files.length,
                })}
              </span>
              <ManageFilesDialog question={question} onSaved={onUpdated} />
            </div>
            {question.files.length === 0 ? (
              <p className="text-xs text-muted-foreground py-1">
                {t("admin.challenge.file.empty")}
              </p>
            ) : (
              <div className="space-y-1">
                {question.files.map((file) => (
                  <div
                    key={file.id}
                    className="flex items-center gap-2 rounded-md border px-3 py-1.5"
                  >
                    <Paperclip className="size-3 text-muted-foreground shrink-0" />
                    <span className="flex-1 text-xs font-medium truncate">{file.name}</span>
                    <span className="text-xs text-muted-foreground">{file.mime_type ?? "—"}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Questions section ─────────────────────────────────────────────────────────

function QuestionsSection({ challengeId }: { challengeId: string }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const { data: solutionTypes = [] } = useQuery({
    queryKey: ["admin", "solution-types"],
    queryFn: getSolutionTypes,
    staleTime: Infinity,
  });

  const qsQuery = `challenge_id=${challengeId}&items_per_page=100&order_by=index&order=asc`;

  const { data: questionsResp } = useQuery({
    queryKey: ["admin", "questions", challengeId],
    queryFn: () => getAdminQuestions(qsQuery),
  });

  const questions = questionsResp?.data ?? [];

  function invalidate() {
    void queryClient.invalidateQueries({
      queryKey: ["admin", "questions", challengeId],
    });
  }

  const reorderMutation = useMutation({
    mutationFn: (updates: { id: string; index: number }[]) =>
      Promise.all(updates.map(({ id, index }) => updateQuestion(id, { index }))),
    onSuccess: invalidate,
    onError: (err) =>
      toast.error(apiErrorMessage(err, t("admin.challenge.question.reorder_error"))),
  });

  function handleMove(i: number, direction: "up" | "down") {
    const j = direction === "up" ? i - 1 : i + 1;
    const reordered = [...questions];
    [reordered[i], reordered[j]] = [reordered[j], reordered[i]];
    const updates = reordered
      .map((q, idx) => ({ id: q.id, index: idx }))
      .filter(
        // biome-ignore lint/style/noNonNullAssertion: id sourced from questions, find always succeeds
        ({ id, index }) => questions.find((q) => q.id === id)!.index !== index,
      );
    reorderMutation.mutate(updates);
  }

  return (
    <DetailSection
      title={t("admin.challenge.question.section_title", {
        count: questions.length,
      })}
      actions={
        <AddQuestionDialog
          challengeId={challengeId}
          questionCount={
            questions.length === 0 ? 0 : Math.max(...questions.map((q) => q.index)) + 1
          }
          onCreated={invalidate}
        />
      }
    >
      {questions.length === 0 ? (
        <div className="rounded-lg border border-dashed px-4 py-10 text-center text-sm text-muted-foreground">
          {t("admin.challenge.question.empty")}
        </div>
      ) : (
        <div className="space-y-2">
          {questions.map((q, i) => (
            <QuestionCard
              key={q.id}
              question={q}
              solutionTypes={solutionTypes}
              isFirst={i === 0}
              isLast={i === questions.length - 1}
              onDeleted={invalidate}
              onUpdated={invalidate}
              onMoveUp={() => handleMove(i, "up")}
              onMoveDown={() => handleMove(i, "down")}
              onCountChanged={invalidate}
            />
          ))}
        </div>
      )}
    </DetailSection>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

function ChallengePage() {
  const { t } = useTranslation();
  const { challengeId } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: challenge, isLoading } = useQuery({
    queryKey: ["admin", "challenge", challengeId],
    queryFn: () => getAdminChallenge(challengeId),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteChallenge(challengeId),
    onSuccess: () => {
      toast.success(t("admin.challenge.deleted"));
      void queryClient.invalidateQueries({ queryKey: ["admin", "challenges"] });
      void navigate({ to: "/admin/challenges" });
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.challenge.delete_error"))),
  });

  if (!isLoading && !challenge) {
    return (
      <DetailPageShell backTo="/admin/challenges" backLabel={t("admin.challenge.back_breadcrumb")}>
        <p className="text-muted-foreground">{t("admin.challenge.not_found")}</p>
      </DetailPageShell>
    );
  }

  return (
    <div className="max-w-3xl">
      <DetailPageShell
        backTo="/admin/challenges"
        backLabel={t("admin.challenge.back_breadcrumb")}
        title={challenge?.title}
        badge={
          challenge && (
            <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
              <Puzzle className="size-3" />
              {challenge.challenge_type}
            </span>
          )
        }
        actions={
          challenge && (
            <Button
              variant="outline"
              size="sm"
              className="text-destructive hover:text-destructive"
              onClick={() => {
                if (
                  confirm(
                    t("admin.challenge.delete_confirm", {
                      title: challenge.title,
                    }),
                  )
                ) {
                  deleteMutation.mutate();
                }
              }}
              disabled={deleteMutation.isPending}
            >
              <Trash2 className="size-4" />
              {t("admin.challenge.delete_btn")}
            </Button>
          )
        }
        isLoading={isLoading}
      >
        {challenge && (
          <>
            <ChallengeInfoSection challenge={challenge} />
            <QuestionsSection challengeId={challengeId} />
          </>
        )}
      </DetailPageShell>
    </div>
  );
}
