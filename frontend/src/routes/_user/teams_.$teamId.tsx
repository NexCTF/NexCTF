import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  ChallengeProgressTable,
  MembersList,
  TeamBadges,
  TeamStatsSummary,
} from "@/components/team-details";
import { getTeamProfile } from "@/lib/api";

export const Route = createFileRoute("/_user/teams_/$teamId")({
  component: TeamProfilePage,
});

function TeamProfilePage() {
  const { teamId } = Route.useParams();
  const { t } = useTranslation();

  const {
    data: team,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["team-profile", teamId],
    queryFn: () => getTeamProfile(teamId),
    staleTime: 60_000,
  });

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 space-y-8">
      <Link
        to="/scoreboard"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="size-4" />
        {t("team.profile_back")}
      </Link>

      {isLoading && <p className="text-muted-foreground text-sm">{t("common.loading")}</p>}
      {error && <p className="text-destructive text-sm">{t("team.profile_load_error")}</p>}

      {team && (
        <>
          <div>
            <h1 className="text-2xl font-bold">{team.name}</h1>
            <TeamBadges team={team} />
          </div>

          <TeamStatsSummary team={team} />

          <MembersList members={team.members} />

          <ChallengeProgressTable stats={team.challenge_stats} />
        </>
      )}
    </div>
  );
}
