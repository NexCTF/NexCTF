import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Navigate } from "@tanstack/react-router";
import { Check, Copy, RefreshCw, Users } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  apiErrorMessage,
  createTeam,
  getMyTeam,
  getPublicInfo,
  joinTeam,
  leaveTeam,
  type MyTeam,
  rotateInviteCode,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { copyToClipboard } from "@/lib/utils";

export const Route = createFileRoute("/_user/team")({
  component: TeamPage,
});

// ── Copy button ───────────────────────────────────────────────────────────────

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);

  function copy() {
    copyToClipboard(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <Button variant="ghost" size="icon" className="size-7 shrink-0" onClick={copy}>
      {copied ? <Check className="size-3.5 text-green-500" /> : <Copy className="size-3.5" />}
    </Button>
  );
}

// ── No team view ──────────────────────────────────────────────────────────────

function NoTeamView({ allowCreation, onJoined }: { allowCreation: boolean; onJoined: () => void }) {
  const { t } = useTranslation();
  const [teamName, setTeamName] = useState("");
  const [code, setCode] = useState("");

  const createMutation = useMutation({
    mutationFn: () => createTeam(teamName),
    onSuccess: () => onJoined(),
    onError: (err) => toast.error(apiErrorMessage(err, t("team.create_error"))),
  });

  const joinMutation = useMutation({
    mutationFn: () => joinTeam(code.trim().toUpperCase()),
    onSuccess: () => onJoined(),
    onError: (err) => toast.error(apiErrorMessage(err, t("team.join_error"))),
  });

  return (
    <div className="mx-auto max-w-2xl px-4 py-10 space-y-8">
      <div>
        <h1 className="text-2xl font-bold">{t("team.title")}</h1>
        <p className="text-muted-foreground text-sm mt-1">{t("team.no_team_hint")}</p>
      </div>

      {allowCreation ? (
        <section className="space-y-4 rounded-lg border p-6">
          <h2 className="text-base font-semibold">{t("team.create_section")}</h2>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              createMutation.mutate();
            }}
            className="flex gap-2"
          >
            <div className="flex-1 space-y-1.5">
              <Label htmlFor="team-name">{t("team.name_label")}</Label>
              <Input
                id="team-name"
                value={teamName}
                onChange={(e) => setTeamName(e.target.value)}
                placeholder={t("team.name_placeholder")}
                required
              />
            </div>
            <div className="flex items-end">
              <Button type="submit" disabled={createMutation.isPending || !teamName.trim()}>
                {createMutation.isPending ? t("team.creating") : t("team.create_btn")}
              </Button>
            </div>
          </form>
        </section>
      ) : (
        <div className="rounded-lg border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
          {t("team.creation_disabled")}
        </div>
      )}

      <section className="space-y-4 rounded-lg border p-6">
        <h2 className="text-base font-semibold">{t("team.join_section")}</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            joinMutation.mutate();
          }}
          className="flex gap-2"
        >
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="invite-code">{t("team.code_label")}</Label>
            <Input
              id="invite-code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder={t("team.code_placeholder")}
              required
            />
          </div>
          <div className="flex items-end">
            <Button type="submit" disabled={joinMutation.isPending || !code.trim()}>
              {joinMutation.isPending ? t("team.joining") : t("team.join_btn")}
            </Button>
          </div>
        </form>
      </section>
    </div>
  );
}

// ── Team view ─────────────────────────────────────────────────────────────────

function TeamView({
  team,
  allowCreation,
  teamSize,
  onLeft,
  onCodeRotated,
}: {
  team: MyTeam;
  allowCreation: boolean;
  teamSize: number;
  onLeft: () => void;
  onCodeRotated: (code: string) => void;
}) {
  const { t, i18n } = useTranslation();

  const leaveMutation = useMutation({
    mutationFn: leaveTeam,
    onSuccess: () => onLeft(),
    onError: (err) => toast.error(apiErrorMessage(err, t("team.leave_error"))),
  });

  const rotateMutation = useMutation({
    mutationFn: rotateInviteCode,
    onSuccess: (code) => onCodeRotated(code),
    onError: (err) => toast.error(apiErrorMessage(err, t("team.invite_rotate_error"))),
  });

  const solvedCount = useMemo(
    () => team.challenge_stats.filter((s) => s.is_solved).length,
    [team.challenge_stats],
  );
  const totalPoints = useMemo(
    () => team.challenge_stats.reduce((sum, s) => sum + s.points_earned, 0),
    [team.challenge_stats],
  );

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 space-y-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{team.name}</h1>
          <p className="text-muted-foreground text-sm mt-1">
            {t("team.member_count", { count: team.members.length, max: teamSize })}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="text-destructive border-destructive/40 hover:bg-destructive/10 hover:text-destructive"
          onClick={() => {
            if (confirm(t("team.leave_confirm", { name: team.name }))) {
              leaveMutation.mutate();
            }
          }}
          disabled={leaveMutation.isPending}
        >
          {t("team.leave_btn")}
        </Button>
      </div>

      {/* Stats summary */}
      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-lg border px-4 py-3 text-center">
          <p className="text-2xl font-bold">{team.members.length}</p>
          <p className="text-xs text-muted-foreground mt-0.5">{t("team.members_title")}</p>
        </div>
        <div className="rounded-lg border px-4 py-3 text-center">
          <p className="text-2xl font-bold">{solvedCount}</p>
          <p className="text-xs text-muted-foreground mt-0.5">{t("team.progress_col_progress")}</p>
        </div>
        <div className="rounded-lg border px-4 py-3 text-center">
          <p className="text-2xl font-bold">{totalPoints}</p>
          <p className="text-xs text-muted-foreground mt-0.5">{t("team.progress_col_points")}</p>
        </div>
      </div>

      {/* Members */}
      <section className="space-y-3">
        <h2 className="text-base font-semibold flex items-center gap-2">
          <Users className="size-4" />
          {t("team.members_title")}
        </h2>
        <div className="space-y-2">
          {team.members.map((m) => (
            <div key={m.id} className="flex items-center gap-3 rounded-lg border px-4 py-2.5">
              <div className="size-7 rounded-full bg-muted flex items-center justify-center text-xs font-medium">
                {m.username[0].toUpperCase()}
              </div>
              <span className="text-sm">{m.username}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Invite code */}
      {allowCreation && team.invite_code && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold">{t("team.invite_section")}</h2>
            <Button
              variant="ghost"
              size="sm"
              className="gap-1.5"
              onClick={() => rotateMutation.mutate()}
              disabled={rotateMutation.isPending}
            >
              <RefreshCw className="size-3.5" />
              {t("team.invite_rotate_btn")}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">{t("team.invite_hint")}</p>
          <div className="flex items-center gap-2 rounded-lg border bg-muted/40 px-3 py-2">
            <code className="flex-1 text-sm font-mono tracking-widest">{team.invite_code}</code>
            <CopyButton value={team.invite_code} />
          </div>
        </section>
      )}

      {/* Challenge progress */}
      <section className="space-y-3">
        <h2 className="text-base font-semibold">{t("team.progress_title")}</h2>

        {team.challenge_stats.length === 0 ? (
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
                  <th className="px-4 py-2.5 text-right font-medium text-muted-foreground hidden sm:table-cell">
                    {t("team.progress_col_solved_at")}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {team.challenge_stats.map((s) => (
                  <tr key={s.challenge_id} className="hover:bg-muted/20 transition-colors">
                    <td className="px-4 py-3">
                      <span className="font-medium">{s.challenge_title}</span>
                    </td>
                    <td className="px-4 py-3">
                      {s.is_solved ? (
                        <span className="inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium text-green-600 bg-green-500/10 ring-1 ring-inset ring-green-500/20">
                          {t("team.solved")}
                        </span>
                      ) : s.solved_question_count > 0 ? (
                        <span className="inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium text-muted-foreground ring-1 ring-inset ring-border">
                          {t("team.partial", {
                            solved: s.solved_question_count,
                            total: s.question_count,
                          })}
                        </span>
                      ) : (
                        <span className="text-muted-foreground text-xs">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">{s.points_earned}</td>
                    <td className="px-4 py-3 text-right text-muted-foreground text-xs hidden sm:table-cell">
                      {s.last_solve_at
                        ? new Date(s.last_solve_at).toLocaleDateString(i18n.language, {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function TeamPage() {
  const { user, isLoading: authLoading } = useAuth();
  const queryClient = useQueryClient();

  const { data: publicInfo } = useQuery({
    queryKey: ["info", "public"],
    queryFn: getPublicInfo,
    staleTime: 5 * 60 * 1000,
  });

  const { data: team, isLoading: teamLoading } = useQuery({
    queryKey: ["my-team"],
    queryFn: getMyTeam,
    enabled: !!user,
  });

  if (authLoading) return null;
  if (!user) return <Navigate to="/login" />;

  if (teamLoading) {
    return (
      <div className="flex items-center justify-center py-32">
        <p className="text-muted-foreground text-sm">Loading…</p>
      </div>
    );
  }

  const allowCreation = publicInfo?.competition.allow_team_creation ?? true;
  const teamSize = publicInfo?.competition.team_size ?? 4;

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ["my-team"] });
    void queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
  }

  function handleCodeRotated(code: string) {
    queryClient.setQueryData(["my-team"], (old: MyTeam | null) =>
      old ? { ...old, invite_code: code } : old,
    );
  }

  if (!team) {
    return <NoTeamView allowCreation={allowCreation} onJoined={invalidate} />;
  }

  return (
    <TeamView
      team={team}
      allowCreation={allowCreation}
      teamSize={teamSize}
      onLeft={invalidate}
      onCodeRotated={handleCodeRotated}
    />
  );
}
