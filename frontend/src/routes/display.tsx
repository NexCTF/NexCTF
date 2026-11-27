import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useLocation } from "@tanstack/react-router";
import { useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { DisplayHeader } from "@/components/display/display-header";
import { DisplayRanking } from "@/components/display/display-ranking";
import { DisplayTicker } from "@/components/display/display-ticker";
import { ScoreEvolutionChart } from "@/components/score-evolution-chart";
import { useCycle } from "@/hooks/use-cycle";
import { useWakeLock } from "@/hooks/use-wake-lock";
import {
  ApiError,
  getScoreboard,
  getScoreboardHistory,
  type ScoreboardEntry,
  type TeamScoreSeries,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { displayTokenFromHash, parseDisplaySearch, resolveDisplayOptions } from "@/lib/display";

export const Route = createFileRoute("/display")({
  validateSearch: parseDisplaySearch,
  component: DisplayPage,
});

const POLL_MS = 10_000;
const CHART_TEAMS = 5;
/** Statuses shown in place of the board, even over data from an earlier poll. */
const REFUSED = [401, 403, 404];
const NO_BRACKETS: string[] = [];
const NO_SERIES: TeamScoreSeries[] = [];

/** Changes whenever a team's total does, so the history is fetched again only then. */
function scoresFingerprint(entries: ScoreboardEntry[] | undefined): string | undefined {
  return entries?.map((e) => `${e.team_id}:${e.total}`).join(",");
}

/**
 * Scoreboard of *bracket*, polled, tagged with the bracket it belongs to (the previous
 * one stays on screen while a new bracket loads), and the history of its top teams.
 */
function useDisplayData(bracket: string | undefined, token: string | null) {
  const lastSuccess = useRef<number | null>(null);
  const board = useQuery({
    queryKey: ["display", "scoreboard", bracket, token],
    queryFn: async () => {
      const data = await getScoreboard(bracket, token);
      lastSuccess.current = Date.now();
      return { bracket, data };
    },
    refetchInterval: POLL_MS,
    refetchIntervalInBackground: true,
    placeholderData: keepPreviousData,
  });
  const shownBracket = board.data?.bracket;
  const entries = board.data?.data.entries;
  const fingerprint = useMemo(() => scoresFingerprint(entries), [entries]);
  const history = useQuery({
    queryKey: ["display", "history", shownBracket, token, CHART_TEAMS, fingerprint],
    queryFn: () => getScoreboardHistory(CHART_TEAMS, shownBracket, token),
    enabled: fingerprint !== undefined,
    refetchInterval: (query) => (query.state.status === "error" ? POLL_MS : false),
    refetchIntervalInBackground: true,
    placeholderData: keepPreviousData,
  });

  return { board, history, lastSuccess };
}

/** Full-screen notice shown instead of the board when it cannot be loaded. */
function DisplayError({
  error,
  bracket,
  hasToken,
}: {
  error: Error;
  bracket: string | undefined;
  hasToken: boolean;
}) {
  const { t } = useTranslation();
  const location = useLocation();
  const status = error instanceof ApiError ? error.status : null;

  let message = t("scoreboard.load_error");
  if (status === 401 && hasToken) {
    message = t("display.token_invalid", {
      defaultValue:
        "This screen link is no longer valid. Create a new one from the admin scoreboard.",
    });
  } else if (status === 401) {
    message = t("display.sign_in_required", {
      defaultValue: "The scoreboard is only visible to signed-in accounts.",
    });
  } else if (status === 403) {
    message = t("display.hidden", {
      defaultValue: "The scoreboard is hidden. Change its visibility in the admin settings.",
    });
  } else if (status === 404 && bracket) {
    message = t("display.unknown_bracket", {
      bracket,
      defaultValue: "No team is in the bracket “{{bracket}}”.",
    });
  }

  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 px-10 text-center">
      <p className="text-3xl text-muted-foreground">{message}</p>
      {status === 401 && !hasToken && (
        <Link
          to="/login"
          search={{ next: location.href }}
          className="cursor-pointer text-2xl text-primary underline underline-offset-4"
        >
          {t("display.sign_in", { defaultValue: "Sign in on this screen" })}
        </Link>
      )}
    </div>
  );
}

function DisplayPage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [token] = useState(() => displayTokenFromHash(window.location.hash));
  const options = resolveDisplayOptions(Route.useSearch());
  const [brackets, setBrackets] = useState(NO_BRACKETS);
  const view = useCycle(brackets.length + 1, options.rotate * 1000);
  const bracket = options.bracket ?? (view === 0 ? undefined : brackets[view - 1]);
  const { board, history, lastSuccess } = useDisplayData(bracket, token);
  useWakeLock();

  const fetchedBrackets = board.data?.data.brackets;
  if (fetchedBrackets && fetchedBrackets !== brackets) setBrackets(fetchedBrackets);

  const refused = board.error instanceof ApiError && REFUSED.includes(board.error.status);
  const shown = refused ? undefined : board.data;

  return (
    <div className="dark">
      <div
        className="fixed inset-0 flex cursor-none flex-col overflow-hidden bg-background text-foreground"
        style={{ zoom: options.scale }}
      >
        <DisplayHeader
          bracket={shown?.bracket}
          lastSuccess={refused ? null : lastSuccess}
          failing={history.isError}
        />
        {shown ? (
          <main className="grid min-h-0 flex-1 grid-cols-[3fr_2fr] gap-6 px-10 py-6">
            <section className="min-h-0">
              <DisplayRanking
                key={shown.bracket ?? ""}
                entries={shown.data.entries}
                showBracket={!shown.bracket && shown.data.brackets.length > 0}
              />
            </section>
            <section className="flex min-h-0 flex-col rounded-xl border px-3 pt-3 pb-2">
              <h2 className="mb-1 px-2 text-xl font-semibold">{t("scoreboard.chart_title")}</h2>
              <div className="min-h-0 flex-1">
                <ScoreEvolutionChart
                  series={history.data?.series ?? NO_SERIES}
                  height="100%"
                  fontSize={16}
                  strokeWidth={3}
                  emptyClassName="text-xl"
                />
              </div>
            </section>
          </main>
        ) : (
          <main className="min-h-0 flex-1">
            {board.error && (
              <DisplayError error={board.error} bracket={bracket} hasToken={token !== null} />
            )}
          </main>
        )}
        {(user || token) && <DisplayTicker token={token} />}
      </div>
    </div>
  );
}
