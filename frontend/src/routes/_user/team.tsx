import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Navigate } from "@tanstack/react-router";
import { Check, Copy, RefreshCw } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { ConfirmDialog } from "@/components/confirm-dialog";
import {
  ChallengeProgressTable,
  MembersList,
  TeamBadges,
  TeamStatsSummary,
} from "@/components/team-details";
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

function NoTeamView({
  allowCreation,
  allowChanges,
  onJoined,
}: {
  allowCreation: boolean;
  allowChanges: boolean;
  onJoined: () => void;
}) {
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

      {!allowChanges ? (
        <div className="rounded-lg border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
          {t("team.changes_disabled")}
        </div>
      ) : (
        <>
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
        </>
      )}
    </div>
  );
}

// ── Team view ─────────────────────────────────────────────────────────────────

function TeamView({
  team,
  allowChanges,
  teamSize,
  onLeft,
  onCodeRotated,
}: {
  team: MyTeam;
  allowChanges: boolean;
  teamSize: number;
  onLeft: () => void;
  onCodeRotated: (code: string) => void;
}) {
  const { t } = useTranslation();

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

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 space-y-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{team.name}</h1>
          <p className="text-muted-foreground text-sm mt-1">
            {t("team.member_count", { n: team.member_count, max: teamSize })}
          </p>
          <TeamBadges team={team} />
        </div>
        {allowChanges ? (
          <ConfirmDialog
            description={t("team.leave_confirm", { name: team.name })}
            confirmLabel={t("team.leave_btn")}
            onConfirm={() => leaveMutation.mutate()}
            trigger={
              <Button
                variant="outline"
                size="sm"
                className="text-destructive border-destructive/40 hover:bg-destructive/10 hover:text-destructive"
                disabled={leaveMutation.isPending}
              >
                {t("team.leave_btn")}
              </Button>
            }
          />
        ) : (
          <p className="text-xs text-muted-foreground max-w-40 text-right">
            {t("team.changes_disabled")}
          </p>
        )}
      </div>

      <TeamStatsSummary team={team} />

      <MembersList members={team.members} />

      {/* Invite code */}
      {allowChanges && (
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

      <ChallengeProgressTable stats={team.challenge_stats} />
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function TeamPage() {
  const { t } = useTranslation();
  const { user, isLoading: authLoading } = useAuth();
  const queryClient = useQueryClient();

  const { data: publicInfo, isLoading: infoLoading } = useQuery({
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

  if (teamLoading || infoLoading) {
    return (
      <div className="flex items-center justify-center py-32">
        <p className="text-muted-foreground text-sm">{t("common.loading")}</p>
      </div>
    );
  }

  const allowCreation = publicInfo?.competition.allow_team_creation ?? true;
  const allowChanges = publicInfo?.competition.allow_team_changes ?? true;
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
    return (
      <NoTeamView allowCreation={allowCreation} allowChanges={allowChanges} onJoined={invalidate} />
    );
  }

  return (
    <TeamView
      team={team}
      allowChanges={allowChanges}
      teamSize={teamSize}
      onLeft={invalidate}
      onCodeRotated={handleCodeRotated}
    />
  );
}
