import { Check, ChevronRight, Lightbulb, Users, X } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";
import { ChallengeLink, DateCell, EmptyCell, SignedPoints } from "@/components/table-cells";
import type { PublicCustomField, PublicTeam, TeamChallengeStats, TeamScoreDetail } from "@/lib/api";

// ── Badges ────────────────────────────────────────────────────────────────────

function TeamBadge({ label, children }: { label: string; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-0.5 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{children}</span>
    </span>
  );
}

function CustomFieldBadges({ fields }: { fields: PublicCustomField[] }) {
  return fields
    .filter((f): f is PublicCustomField & { value: string } => Boolean(f.value))
    .map((f) => (
      <TeamBadge key={f.name} label={f.label}>
        {f.field_type === "url" && /^https?:\/\//i.test(f.value) ? (
          <a
            href={f.value}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline underline-offset-2"
          >
            {f.value}
          </a>
        ) : (
          f.value
        )}
      </TeamBadge>
    ));
}

export function TeamBadges({ team }: { team: PublicTeam }) {
  const { t } = useTranslation();
  const hasFields = team.custom_fields.some((f) => Boolean(f.value));
  if (!team.country && !team.bracket && !hasFields) return null;

  return (
    <div className="flex flex-wrap gap-1.5 mt-3">
      {team.country && <TeamBadge label={t("team.country_label")}>{team.country}</TeamBadge>}
      {team.bracket && (
        <TeamBadge label={t("team.bracket_label")}>
          <span className="capitalize">{team.bracket}</span>
        </TeamBadge>
      )}
      <CustomFieldBadges fields={team.custom_fields} />
    </div>
  );
}

// ── Stats summary ─────────────────────────────────────────────────────────────

function StatBox({ value, label }: { value: ReactNode; label: string }) {
  return (
    <div className="rounded-lg border px-4 py-3 text-center">
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-xs text-muted-foreground mt-0.5">{label}</p>
    </div>
  );
}

/** Percentage of questions the team has solved, across every challenge. */
export function progressPercent(stats: TeamChallengeStats[]) {
  const total = stats.reduce((sum, s) => sum + s.question_count, 0);
  const solved = stats.reduce((sum, s) => sum + s.solved_question_count, 0);
  return total > 0 ? Math.round((solved / total) * 100) : 0;
}

export function TeamStatsSummary({ team }: { team: PublicTeam }) {
  const { t } = useTranslation();
  const totalPoints = team.challenge_stats.reduce((sum, s) => sum + s.points_earned, 0);
  const completion = progressPercent(team.challenge_stats);

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
      <StatBox
        value={
          team.rank !== null ? (
            <>
              #{team.rank}
              <span className="text-sm font-medium text-muted-foreground">
                {" "}
                / {team.team_count}
              </span>
            </>
          ) : (
            "—"
          )
        }
        label={t("team.rank_label")}
      />
      <StatBox value={team.member_count} label={t("team.members_title")} />
      <StatBox value={`${completion}%`} label={t("team.progress_col_progress")} />
      <StatBox value={team.score ?? totalPoints} label={t("team.progress_col_points")} />
    </div>
  );
}

// ── Score breakdown ───────────────────────────────────────────────────────────

export function ScoreBreakdown({ score }: { score: TeamScoreDetail }) {
  const { t } = useTranslation();

  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold">{t("team.score_breakdown_title")}</h2>
      <div className="rounded-lg border divide-y">
        <div className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
          <span>{t("team.solve_points_label")}</span>
          <span className="font-medium tabular-nums">{score.solve_points + score.hint_points}</span>
        </div>
        <details className="group">
          <summary className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm cursor-pointer hover:bg-muted/20 transition-colors list-none [&::-webkit-details-marker]:hidden">
            <span className="flex items-center gap-2">
              <ChevronRight className="size-3.5 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" />
              {t("team.adjustments_label")}
            </span>
            <SignedPoints amount={score.adjustment_points} />
          </summary>
          <div className="divide-y bg-muted/10 px-4 py-1">
            {score.adjustments.length === 0 && (
              <p className="py-2 pl-6 text-xs text-muted-foreground">
                {t("team.adjustments_empty")}
              </p>
            )}
            {score.adjustments.map((adj) => (
              <div
                key={adj.id}
                className="flex items-center justify-between gap-3 py-2 pl-6 text-xs"
              >
                <span>
                  {adj.reason}
                  {adj.challenge_title && (
                    <span className="text-muted-foreground"> — {adj.challenge_title}</span>
                  )}
                </span>
                <SignedPoints amount={adj.amount} />
              </div>
            ))}
          </div>
        </details>
        <div className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
          <span className="font-semibold">{t("team.total_label")}</span>
          <span className="font-semibold tabular-nums">{score.total}</span>
        </div>
      </div>
    </section>
  );
}

// ── Members ───────────────────────────────────────────────────────────────────

export function MembersList({ members }: { members: PublicTeam["members"] }) {
  const { t } = useTranslation();
  if (!members) return null;
  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold flex items-center gap-2">
        <Users className="size-4" />
        {t("team.members_title")}
      </h2>
      <div className="space-y-2">
        {members.map((m) => (
          <div
            key={m.id}
            className="flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-lg border px-4 py-2.5"
          >
            <div className="size-7 rounded-full bg-muted flex items-center justify-center text-xs font-medium">
              {m.username[0].toUpperCase()}
            </div>
            <span className="text-sm">{m.username}</span>
            <CustomFieldBadges fields={m.custom_fields} />
          </div>
        ))}
      </div>
    </section>
  );
}

// ── Challenge progress ────────────────────────────────────────────────────────

function ChallengeStatsRow({ stats, detailed }: { stats: TeamChallengeStats; detailed: boolean }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const expandable = stats.questions.length > 0;

  return (
    <>
      <tr
        className={`hover:bg-muted/20 transition-colors ${expandable ? "cursor-pointer" : ""}`}
        onClick={() => expandable && setOpen((o) => !o)}
      >
        <td className="px-4 py-3">
          <span className="flex items-center gap-2 font-medium">
            <ChevronRight
              className={`size-3.5 shrink-0 text-muted-foreground transition-transform ${
                open ? "rotate-90" : ""
              } ${expandable ? "" : "invisible"}`}
            />
            {detailed ? (
              <ChallengeLink id={stats.challenge_id} name={stats.challenge_title} />
            ) : (
              stats.challenge_title
            )}
          </span>
        </td>
        <td className="px-4 py-3">
          <span
            className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${
              stats.is_solved
                ? "text-green-600 bg-green-500/10 ring-green-500/20"
                : "text-muted-foreground ring-border"
            }`}
          >
            {t("team.partial", {
              solved: stats.solved_question_count,
              total: stats.question_count,
            })}
          </span>
        </td>
        <td className="px-4 py-3 text-right tabular-nums">{stats.points_earned}</td>
      </tr>
      {open && (
        <tr className="bg-muted/10">
          <td colSpan={3} className="px-4 py-1">
            <div className="divide-y">
              {stats.questions.map((q) => (
                <div key={q.question_id} className="py-2 pl-6 text-xs">
                  <div className="flex items-center justify-between">
                    <span>{q.question_label}</span>
                    <span className="flex items-center gap-4 text-muted-foreground">
                      {q.wrong_attempt_count > 0 && (
                        <span className="flex items-center gap-1">
                          <X className="size-3 text-red-500" />
                          {t("team.attempts_failed", { count: q.wrong_attempt_count })}
                        </span>
                      )}
                      {q.hint_unlock_count > 0 && (
                        <span className="flex items-center gap-1">
                          <Lightbulb className="size-3" />
                          {t("team.hints_used", { count: q.hint_unlock_count })}
                        </span>
                      )}
                      {q.is_solved && <SignedPoints amount={q.points_earned} />}
                      {q.solved_at && <DateCell value={q.solved_at} />}
                      {q.is_solved ? <Check className="size-3.5 text-green-500" /> : <EmptyCell />}
                    </span>
                  </div>
                  {q.hints?.map((h) => (
                    <div
                      key={h.hint_id}
                      className="flex items-center justify-between gap-4 pt-1.5 pl-6 text-xs text-muted-foreground"
                    >
                      <span className="flex items-center gap-1.5">
                        <Lightbulb className="size-3" />
                        {h.title}
                      </span>
                      <span className="flex items-center gap-4">
                        <SignedPoints amount={-h.cost_paid} />
                        <DateCell value={h.unlocked_at} />
                      </span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

/** `detailed` is the admin variant: challenges link to the admin pages and the
 * caller owns the heading. The extra per-question rows (solve date, unlocked
 * hints) come from the admin payload itself. */
export function ChallengeProgressTable({
  stats,
  detailed = false,
}: {
  stats: TeamChallengeStats[];
  detailed?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <section className="space-y-3">
      {!detailed && <h2 className="text-base font-semibold">{t("team.progress_title")}</h2>}

      {stats.length === 0 ? (
        <div className="rounded-lg border border-dashed px-4 py-10 text-center text-sm text-muted-foreground">
          {t("team.progress_empty")}
        </div>
      ) : (
        <div className="rounded-lg border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/40">
              <tr>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">
                  {t("team.progress_col_challenge")}
                </th>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">
                  {t("team.progress_col_progress")}
                </th>
                <th className="px-4 py-2.5 text-right font-medium text-muted-foreground">
                  {t("team.progress_col_points")}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {stats.map((s) => (
                <ChallengeStatsRow key={s.challenge_id} stats={s} detailed={detailed} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
