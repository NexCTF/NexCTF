import { Check, ChevronRight, Lightbulb, Users } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";
import type { PublicCustomField, PublicTeam, TeamChallengeStats } from "@/lib/api";

// ── Badges ────────────────────────────────────────────────────────────────────

function TeamBadge({ label, children }: { label: string; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-0.5 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{children}</span>
    </span>
  );
}

export function TeamBadges({ team }: { team: PublicTeam }) {
  const { t } = useTranslation();
  const fields = team.custom_fields.filter((f): f is PublicCustomField & { value: string } =>
    Boolean(f.value),
  );
  if (!team.country && !team.bracket && fields.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5 mt-3">
      {team.country && <TeamBadge label={t("team.country_label")}>{team.country}</TeamBadge>}
      {team.bracket && (
        <TeamBadge label={t("team.bracket_label")}>
          <span className="capitalize">{team.bracket}</span>
        </TeamBadge>
      )}
      {fields.map((f) => (
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
      ))}
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

export function TeamStatsSummary({ team }: { team: PublicTeam }) {
  const { t } = useTranslation();
  const totalQuestions = team.challenge_stats.reduce((sum, s) => sum + s.question_count, 0);
  const solvedQuestions = team.challenge_stats.reduce((sum, s) => sum + s.solved_question_count, 0);
  const totalPoints = team.challenge_stats.reduce((sum, s) => sum + s.points_earned, 0);
  const completion = totalQuestions > 0 ? Math.round((solvedQuestions / totalQuestions) * 100) : 0;

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
      <StatBox value={team.members.length} label={t("team.members_title")} />
      <StatBox value={`${completion}%`} label={t("team.progress_col_progress")} />
      <StatBox value={totalPoints} label={t("team.progress_col_points")} />
    </div>
  );
}

// ── Members ───────────────────────────────────────────────────────────────────

export function MembersList({ members }: { members: PublicTeam["members"] }) {
  const { t } = useTranslation();
  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold flex items-center gap-2">
        <Users className="size-4" />
        {t("team.members_title")}
      </h2>
      <div className="space-y-2">
        {members.map((m) => (
          <div key={m.id} className="flex items-center gap-3 rounded-lg border px-4 py-2.5">
            <div className="size-7 rounded-full bg-muted flex items-center justify-center text-xs font-medium">
              {m.username[0].toUpperCase()}
            </div>
            <span className="text-sm">{m.username}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

// ── Challenge progress ────────────────────────────────────────────────────────

function ChallengeStatsRow({ stats }: { stats: TeamChallengeStats }) {
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
            {stats.challenge_title}
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
                <div
                  key={q.question_id}
                  className="flex items-center justify-between py-2 pl-6 text-xs"
                >
                  <span>{q.question_label}</span>
                  <span className="flex items-center gap-4 text-muted-foreground">
                    {q.hint_unlock_count > 0 && (
                      <span className="flex items-center gap-1">
                        <Lightbulb className="size-3" />
                        {t("team.hints_used", { count: q.hint_unlock_count })}
                      </span>
                    )}
                    {q.is_solved ? <Check className="size-3.5 text-green-500" /> : <span>—</span>}
                  </span>
                </div>
              ))}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export function ChallengeProgressTable({ stats }: { stats: TeamChallengeStats[] }) {
  const { t } = useTranslation();
  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold">{t("team.progress_title")}</h2>

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
                <ChallengeStatsRow key={s.challenge_id} stats={s} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
