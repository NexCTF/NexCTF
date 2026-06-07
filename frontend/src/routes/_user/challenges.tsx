import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, Navigate } from "@tanstack/react-router";
import { AlertTriangle, CheckCircle2, ChevronRight, Circle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { TagBadge } from "@/components/tag-badge";
import { getChallenges, type PublicChallenge } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useEventEnded } from "@/lib/use-event-ended";

export const Route = createFileRoute("/_user/challenges")({
  component: ChallengesPage,
});

function ChallengesPage() {
  const { t } = useTranslation();
  const { user, isLoading: authLoading } = useAuth();

  const { data: challenges = [], isLoading } = useQuery({
    queryKey: ["challenges"],
    queryFn: getChallenges,
    enabled: !!user,
  });

  const eventEnded = useEventEnded();

  if (authLoading) return null;
  if (!user) return <Navigate to="/login" />;

  // Group by category
  const grouped = new Map<string, PublicChallenge[]>();
  for (const c of challenges) {
    const key = c.category_name ?? "Uncategorized";
    if (!grouped.has(key)) grouped.set(key, []);
    // biome-ignore lint/style/noNonNullAssertion: key guaranteed by grouped.set above
    grouped.get(key)!.push(c);
  }

  return (
    <div className="mx-auto max-w-screen-lg px-4 py-10 space-y-10">
      {eventEnded && (
        <div className="flex items-center gap-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-700 dark:text-amber-400">
          <AlertTriangle className="size-4 shrink-0" />
          {t("challenge.event_ended_banner")}
        </div>
      )}
      <h1 className="text-2xl font-bold">Challenges</h1>

      {isLoading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : challenges.length === 0 ? (
        <p className="text-muted-foreground">No challenges available yet.</p>
      ) : (
        Array.from(grouped.entries()).map(([category, items]) => (
          <section key={category} className="space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground">
              {category}
            </h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {items.map((c) => (
                <ChallengeCard key={c.id} challenge={c} />
              ))}
            </div>
          </section>
        ))
      )}
    </div>
  );
}

function ChallengeCard({ challenge: c }: { challenge: PublicChallenge }) {
  const pct = c.question_count > 0 ? Math.round((c.solved_count / c.question_count) * 100) : 0;
  const done = c.solved_count === c.question_count && c.question_count > 0;

  return (
    <Link
      to="/challenges/$challengeId"
      params={{ challengeId: c.id }}
      className="group flex flex-col gap-3 rounded-xl border bg-card p-5 transition-colors hover:border-primary hover:bg-muted/30"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="font-semibold leading-snug group-hover:text-primary transition-colors">
          {c.title}
        </span>
        <ChevronRight className="size-4 shrink-0 text-muted-foreground mt-0.5 group-hover:text-primary transition-colors" />
      </div>

      {c.tags && c.tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {c.tags.map((tag) => (
            <TagBadge key={tag.id} tag={tag} />
          ))}
        </div>
      )}

      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        {done ? (
          <CheckCircle2 className="size-4 text-green-500 shrink-0" />
        ) : (
          <Circle className="size-4 shrink-0" />
        )}
        <span>
          {c.solved_count}/{c.question_count} question
          {c.question_count !== 1 ? "s" : ""}
        </span>
      </div>

      <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full bg-primary transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
    </Link>
  );
}
