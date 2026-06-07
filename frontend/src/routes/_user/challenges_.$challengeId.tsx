import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, Navigate } from "@tanstack/react-router";
import {
  AlertTriangle,
  AlignLeft,
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Code2,
  Eye,
  FileText,
  Lightbulb,
  Lock,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Markdown } from "@/components/markdown";
import { PluginSlot } from "@/components/plugin-slot";
import { TagBadge } from "@/components/tag-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  apiErrorMessage,
  getChallenge,
  type InputType,
  type PublicChallengeDetail,
  type PublicHint,
  type PublicQuestion,
  submitAnswer,
  unlockHint,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useEventEnded } from "@/lib/use-event-ended";
import { formatBytes } from "@/lib/utils";

export const Route = createFileRoute("/_user/challenges_/$challengeId")({
  component: ChallengePage,
});

function ChallengePage() {
  const { t } = useTranslation();
  const { challengeId } = Route.useParams();
  const { user, isLoading: authLoading } = useAuth();

  const { data: challenge, isLoading } = useQuery({
    queryKey: ["challenge", challengeId],
    queryFn: () => getChallenge(challengeId),
    enabled: !!user,
    refetchOnWindowFocus: false,
    staleTime: 30_000,
  });

  if (authLoading) return null;
  if (!user) return <Navigate to="/login" />;

  if (isLoading) {
    return (
      <div className="mx-auto max-w-screen-md px-4 py-20 text-center text-muted-foreground">
        {t("challenge.loading")}
      </div>
    );
  }

  if (!challenge) return null;

  return <ChallengeView challenge={challenge} />;
}

function ChallengeView({ challenge }: { challenge: PublicChallengeDetail }) {
  const { t } = useTranslation();
  const pct =
    challenge.question_count > 0
      ? Math.round((challenge.solved_count / challenge.question_count) * 100)
      : 0;
  const pluginContext = useMemo(() => ({ challenge }), [challenge]);

  const eventEnded = useEventEnded();

  return (
    <div className="mx-auto max-w-screen-md px-4 py-8 space-y-8">
      {eventEnded && (
        <div className="flex items-center gap-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-700 dark:text-amber-400">
          <AlertTriangle className="size-4 shrink-0" />
          {t("challenge.event_ended_banner")}
        </div>
      )}
      <div className="space-y-4">
        <Link
          to="/challenges"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="size-4" /> {t("challenge.back")}
        </Link>

        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-2xl font-bold">{challenge.title}</h1>
            {challenge.category_name && (
              <span className="inline-flex items-center rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
                {challenge.category_name}
              </span>
            )}
            {challenge.sequential && (
              <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
                {t("challenge.sequential")}
              </span>
            )}
            {challenge.tags?.map((tag) => (
              <TagBadge key={tag.id} tag={tag} />
            ))}
          </div>
          {challenge.description && (
            <Markdown className="text-sm text-muted-foreground">{challenge.description}</Markdown>
          )}
        </div>

        <div className="space-y-1.5">
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>
              {t("challenge.progress", {
                solved: challenge.solved_count,
                total: challenge.question_count,
              })}
            </span>
            <span>{pct}%</span>
          </div>
          <div className="h-2 rounded-full bg-muted overflow-hidden">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      </div>

      <PluginSlot
        name="challenge_panel"
        challengeType={challenge.challenge_type}
        context={pluginContext}
      />

      <div className="space-y-4">
        {challenge.questions.map((q, i) => (
          <QuestionCard key={q.id} question={q} index={i} challengeId={challenge.id} />
        ))}
      </div>
    </div>
  );
}

function QuestionCard({
  question: q,
  index,
  challengeId,
}: {
  question: PublicQuestion;
  index: number;
  challengeId: string;
}) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(!q.is_solved && !q.is_locked);
  const queryClient = useQueryClient();

  function refetch() {
    void queryClient.invalidateQueries({
      queryKey: ["challenge", challengeId],
    });
  }

  if (q.is_locked) {
    return (
      <div className="rounded-xl border bg-muted/30 opacity-60 select-none">
        <div className="w-full flex items-center gap-3 px-5 py-4">
          <Lock className="size-5 text-muted-foreground shrink-0" />
          <span className="flex-1 font-medium text-muted-foreground blur-sm">{q.label}</span>
          <span className="text-sm text-muted-foreground shrink-0">
            {q.points} pts{q.malus != null ? ` / −${q.malus}` : ""}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`rounded-xl border transition-colors ${
        q.is_solved ? "border-green-500/40 bg-green-500/5" : "bg-card"
      }`}
    >
      {/* Question header */}
      <button
        type="button"
        className="w-full flex items-center gap-3 px-5 py-4 text-left"
        onClick={() => setExpanded((v) => !v)}
      >
        {q.is_solved ? (
          <CheckCircle2 className="size-5 text-green-500 shrink-0" />
        ) : (
          <span className="size-5 shrink-0 flex items-center justify-center rounded-full border text-xs font-mono text-muted-foreground">
            {index + 1}
          </span>
        )}
        <span className="flex-1 font-medium">{q.label}</span>
        {q.input_type === "code" && (
          <span className="shrink-0 inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs text-muted-foreground font-mono">
            <Code2 className="size-3" />
            code
          </span>
        )}
        {q.input_type === "text" && (
          <span className="shrink-0 inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs text-muted-foreground">
            <AlignLeft className="size-3" />
            text
          </span>
        )}
        {q.input_type === "mcq" && (
          <span className="shrink-0 inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs text-muted-foreground">
            MCQ
          </span>
        )}
        <span className="text-sm text-muted-foreground shrink-0">
          {q.points} pts{q.malus != null ? ` / −${q.malus}` : ""}
        </span>
        {expanded ? (
          <ChevronUp className="size-4 text-muted-foreground shrink-0" />
        ) : (
          <ChevronDown className="size-4 text-muted-foreground shrink-0" />
        )}
      </button>

      {expanded && (
        <div className="px-5 pb-5 space-y-5 border-t pt-5">
          {q.tags && q.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {q.tags.map((tag) => (
                <TagBadge key={tag.id} tag={tag} />
              ))}
            </div>
          )}

          {q.description && (
            <Markdown className="text-sm text-muted-foreground">{q.description}</Markdown>
          )}

          {q.files.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {t("challenge.files")}
              </p>
              <div className="flex flex-wrap gap-2">
                {q.files.map((f) => (
                  <a
                    key={f.id}
                    href={f.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm hover:border-primary hover:bg-muted/50 transition-colors"
                  >
                    <FileText className="size-3.5 text-muted-foreground" />
                    {f.name}
                    {f.file_size != null && (
                      <span className="text-xs text-muted-foreground">
                        ({formatBytes(f.file_size)})
                      </span>
                    )}
                  </a>
                ))}
              </div>
            </div>
          )}

          {q.hints.length > 0 && (
            <HintsSection
              hints={q.hints}
              challengeId={challengeId}
              questionId={q.id}
              onUnlocked={refetch}
            />
          )}

          {!q.is_solved && (
            <SubmitSection
              challengeId={challengeId}
              questionId={q.id}
              inputType={q.input_type ?? "input"}
              options={q.options ?? null}
              multiSelect={q.multi_select ?? false}
              onSolved={refetch}
            />
          )}

          {q.is_solved && (
            <p className="text-sm text-green-600 dark:text-green-400 font-medium text-center py-1">
              {t("challenge.solved")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function HintsSection({
  hints,
  challengeId,
  questionId,
  onUnlocked,
}: {
  hints: PublicHint[];
  challengeId: string;
  questionId: string;
  onUnlocked: () => void;
}) {
  const { t } = useTranslation();
  const unlockMutation = useMutation({
    mutationFn: (hintId: string) => unlockHint(challengeId, questionId, hintId),
    onSuccess: onUnlocked,
    onError: (err) => toast.error(apiErrorMessage(err, t("challenge.hint_unlock_error"))),
  });

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {t("challenge.hints")}
      </p>
      <div className="space-y-2">
        {hints.map((h) => (
          <div key={h.id} className="rounded-lg border px-4 py-3 text-sm space-y-1">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Lightbulb className="size-4 text-yellow-500 shrink-0" />
                <span className="font-medium">{h.title}</span>
              </div>
              {!h.is_unlocked && (
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs shrink-0"
                  onClick={() => {
                    if (
                      h.cost === 0 ||
                      confirm(t("challenge.hint_unlock_confirm", { cost: h.cost }))
                    ) {
                      unlockMutation.mutate(h.id);
                    }
                  }}
                  disabled={unlockMutation.isPending}
                >
                  <Lock className="size-3 mr-1" />
                  {h.cost > 0 ? `−${h.cost} pts` : t("challenge.hint_unlock_btn")}
                </Button>
              )}
              {h.is_unlocked && <Eye className="size-4 text-muted-foreground shrink-0" />}
            </div>
            {h.is_unlocked && h.content && (
              <p className="text-muted-foreground leading-relaxed pl-6">{h.content}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function SubmitSection({
  challengeId,
  questionId,
  inputType,
  options,
  multiSelect = false,
  onSolved,
}: {
  challengeId: string;
  questionId: string;
  inputType: InputType;
  options?: string[] | null;
  multiSelect?: boolean;
  onSolved: () => void;
}) {
  const { t } = useTranslation();
  const [answer, setAnswer] = useState("");
  const [selected, setSelected] = useState<string[]>([]);

  const submitMutation = useMutation({
    mutationFn: (payload: string) => submitAnswer(challengeId, questionId, payload),
    onSuccess: (result) => {
      if (result.is_correct) {
        toast.success(result.message);
        setAnswer("");
        setSelected([]);
        onSolved();
      } else {
        toast.error(result.message);
      }
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("challenge.submit_error"))),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputType === "mcq" && multiSelect) {
      if (selected.length === 0) return;
      submitMutation.mutate(JSON.stringify(selected.slice().sort()));
    } else {
      if (!answer.trim()) return;
      submitMutation.mutate(answer);
    }
  };

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {t("challenge.answer_label")}
      </p>
      <form onSubmit={handleSubmit} className="space-y-2">
        {inputType === "input" && (
          <div className="flex gap-2">
            <Input
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder={t("challenge.answer_placeholder")}
              className="font-mono"
              autoComplete="off"
              spellCheck={false}
            />
            <Button type="submit" disabled={!answer.trim() || submitMutation.isPending}>
              {submitMutation.isPending ? t("challenge.submitting") : t("challenge.submit")}
            </Button>
          </div>
        )}
        {inputType === "text" && (
          <>
            <Textarea
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder={t("challenge.answer_placeholder")}
              rows={5}
              spellCheck={false}
            />
            <Button
              type="submit"
              disabled={!answer.trim() || submitMutation.isPending}
              className="w-full"
            >
              {submitMutation.isPending ? t("challenge.submitting") : t("challenge.submit")}
            </Button>
          </>
        )}
        {inputType === "code" && (
          <>
            <Textarea
              value={answer}
              onChange={(e) => {
                setAnswer(e.target.value);
              }}
              onKeyDown={(e) => {
                if (e.key === "Tab") {
                  e.preventDefault();
                  const el = e.currentTarget;
                  const start = el.selectionStart;
                  const end = el.selectionEnd;
                  const next = `${answer.substring(0, start)}  ${answer.substring(end)}`;
                  setAnswer(next);
                  requestAnimationFrame(() => {
                    el.selectionStart = el.selectionEnd = start + 2;
                  });
                }
              }}
              placeholder={t("challenge.answer_placeholder")}
              className="font-mono text-sm"
              rows={8}
              spellCheck={false}
            />
            <Button
              type="submit"
              disabled={!answer.trim() || submitMutation.isPending}
              className="w-full"
            >
              {submitMutation.isPending ? t("challenge.submitting") : t("challenge.submit")}
            </Button>
          </>
        )}
        {inputType === "mcq" && (
          <>
            <div className="space-y-2">
              {(options ?? []).map((opt) => {
                const isChecked = multiSelect ? selected.includes(opt) : answer === opt;
                return (
                  <label
                    key={opt}
                    className={`flex items-center gap-3 rounded-lg border px-4 py-3 cursor-pointer transition-colors ${
                      isChecked
                        ? "border-primary bg-primary/5"
                        : "hover:border-muted-foreground/40 hover:bg-muted/40"
                    }`}
                  >
                    <input
                      type={multiSelect ? "checkbox" : "radio"}
                      name={`mcq-${questionId}`}
                      value={opt}
                      checked={isChecked}
                      onChange={() => {
                        if (multiSelect) {
                          setSelected((prev) =>
                            prev.includes(opt) ? prev.filter((s) => s !== opt) : [...prev, opt],
                          );
                        } else {
                          setAnswer(opt);
                        }
                      }}
                      className="accent-primary"
                    />
                    <span className="text-sm">{opt}</span>
                  </label>
                );
              })}
            </div>
            <Button
              type="submit"
              disabled={submitMutation.isPending || (multiSelect ? selected.length === 0 : !answer)}
              className="w-full"
            >
              {submitMutation.isPending ? t("challenge.submitting") : t("challenge.submit")}
            </Button>
          </>
        )}
      </form>
    </div>
  );
}
