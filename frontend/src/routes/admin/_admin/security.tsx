import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { RefreshCw, ShieldAlert } from "lucide-react";
import { memo, useDeferredValue, useState } from "react";
import { useTranslation } from "react-i18next";
import { BetaBadge } from "@/components/beta-badge";
import { PageHeader } from "@/components/page-header";
import { SearchInput } from "@/components/search-input";
import { StatCard } from "@/components/stat-card";
import { StatusBadge } from "@/components/status-badge";
import { TeamLink, UserLink } from "@/components/table-cells";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  type FailedLoginAddress,
  getAdminSessionAddresses,
  getAdminSessionFailedLogins,
  SESSION_WINDOWS,
  type SessionOverview,
  type SessionWindow,
  type SharedAddress,
  type SharedAddressAccount,
} from "@/lib/api";
import { describeDevice, formatLastSeen } from "@/lib/session";

const TABS = ["sessions", "failed-logins"] as const;

type SecurityTab = (typeof TABS)[number];

// Nothing is live about a failed login, so that view starts one window wider.
const FAILED_WINDOWS: readonly SessionWindow[] = ["day", "all"];

export const Route = createFileRoute("/admin/_admin/security")({
  component: SecurityPage,
  validateSearch: (search: Record<string, unknown>): { tab: SecurityTab } => ({
    tab: TABS.includes(search.tab as SecurityTab) ? (search.tab as SecurityTab) : "sessions",
  }),
});

function TabNav({ active }: { active: SecurityTab }) {
  const { t } = useTranslation();
  const navigate = Route.useNavigate();
  const labels: Record<SecurityTab, string> = {
    sessions: t("admin.security.tab_sessions", { defaultValue: "Sessions" }),
    "failed-logins": t("admin.security.tab_failed_logins", { defaultValue: "Failed logins" }),
  };

  return (
    <div className="flex gap-6 border-b">
      {TABS.map((tab) => (
        <button
          key={tab}
          type="button"
          aria-pressed={tab === active}
          onClick={() => void navigate({ search: { tab } })}
          className={`-mb-px border-b-2 px-1 pb-2 text-sm font-medium transition-colors ${
            tab === active
              ? "border-primary text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          {labels[tab]}
        </button>
      ))}
    </div>
  );
}

function WindowSwitch({
  value,
  options,
  onChange,
}: {
  value: SessionWindow;
  options: readonly SessionWindow[];
  onChange: (window: SessionWindow) => void;
}) {
  const { t } = useTranslation();
  const labels: Record<SessionWindow, string> = {
    live: t("admin.sessions.window_live", { defaultValue: "Live now" }),
    day: t("admin.sessions.window_day", { defaultValue: "Last 24 hours" }),
    all: t("admin.sessions.window_all", { defaultValue: "Whole event" }),
  };

  return (
    <fieldset
      className="flex gap-1"
      aria-label={t("admin.sessions.window_label", { defaultValue: "Window" })}
    >
      {options.map((option) => (
        <Button
          key={option}
          size="sm"
          variant={option === value ? "default" : "outline"}
          aria-pressed={option === value}
          onClick={() => onChange(option)}
        >
          {labels[option]}
        </Button>
      ))}
    </fieldset>
  );
}

function RefreshButton({ onClick, busy }: { onClick: () => void; busy: boolean }) {
  const { t } = useTranslation();
  return (
    <Button
      variant="outline"
      size="icon-sm"
      onClick={onClick}
      disabled={busy}
      aria-label={t("common.refresh", { defaultValue: "Refresh" })}
    >
      <RefreshCw className={`size-3.5 ${busy ? "animate-spin" : ""}`} />
    </Button>
  );
}

function TeamBadge({ address }: { address: SharedAddress }) {
  const { t } = useTranslation();
  if (address.same_team) {
    return (
      <StatusBadge tone="muted">
        {t("admin.sessions.same_team", { defaultValue: "Same team" })}
      </StatusBadge>
    );
  }
  if (address.team_count < 2) return null;
  return (
    <StatusBadge tone="amber">
      {t("admin.sessions.cross_team", { defaultValue: "Different teams" })}
    </StatusBadge>
  );
}

function AccountRow({ account, live }: { account: SharedAddressAccount; live: boolean }) {
  const { t, i18n } = useTranslation();
  const { browser, os, icon: DeviceIcon } = describeDevice(account.user_agent);
  const volume = live
    ? t("admin.sessions.account_sessions", {
        total: account.session_count,
        defaultValue: "{{total}} sessions",
      })
    : t("admin.sessions.account_logins", {
        total: account.session_count,
        defaultValue: "{{total}} logins",
      });
  const meta = [
    [browser, os].filter(Boolean).join(" "),
    account.session_count > 1 ? volume : "",
    formatLastSeen(account.last_seen_at, i18n.language),
  ].filter(Boolean);

  return (
    <div className="space-y-1 rounded-lg border px-3 py-2">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <UserLink id={account.user_id} name={account.username} />
        <TeamLink id={account.team_id} name={account.team_name} />
        {!account.opened_here && (
          <StatusBadge tone="amber">
            {t("admin.sessions.moved_here", { defaultValue: "Moved here" })}
          </StatusBadge>
        )}
      </div>
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        {account.user_agent && <DeviceIcon className="size-3 shrink-0" />}
        {meta.join(" · ")}
      </p>
    </div>
  );
}

const AddressCard = memo(function AddressCard({
  address,
  live,
}: {
  address: SharedAddress;
  live: boolean;
}) {
  const { t, i18n } = useTranslation();
  const summary = [
    t("admin.sessions.address_accounts", {
      count: address.account_count,
      defaultValue: "{{count}} account",
      defaultValue_other: "{{count}} accounts",
    }),
    formatLastSeen(address.last_seen_at, i18n.language),
  ].join(" · ");

  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <code className="rounded bg-muted px-2 py-1 font-mono text-sm">{address.ip}</code>
          {address.account_count > 1 && <TeamBadge address={address} />}
        </div>
        <p className="text-xs text-muted-foreground">{summary}</p>
        <div className="space-y-2">
          {address.accounts.map((account) => (
            <AccountRow key={account.user_id} account={account} live={live} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
});

function SessionSummary({ overview, live }: { overview: SessionOverview; live: boolean }) {
  const { t } = useTranslation();
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      <StatCard
        label={
          live
            ? t("admin.sessions.stat_sessions", { defaultValue: "Live sessions" })
            : t("admin.sessions.stat_logins", { defaultValue: "Logins" })
        }
        value={overview.session_count}
      />
      <StatCard
        label={t("admin.sessions.stat_accounts", { defaultValue: "Accounts signed in" })}
        value={overview.account_count}
      />
      <StatCard
        label={t("admin.sessions.stat_addresses", { defaultValue: "Addresses" })}
        value={overview.address_count}
      />
      <StatCard
        label={t("admin.sessions.stat_shared", { defaultValue: "Shared addresses" })}
        value={overview.shared_address_count}
      />
      <StatCard
        label={t("admin.sessions.stat_cross_team", { defaultValue: "Across teams" })}
        value={overview.cross_team_address_count}
      />
    </div>
  );
}

function SessionsTab() {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const [showAll, setShowAll] = useState(false);
  const [sessionWindow, setSessionWindow] = useState<SessionWindow>("live");
  const live = sessionWindow === "live";

  const {
    data: overview,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["admin", "session-addresses", sessionWindow],
    queryFn: () => getAdminSessionAddresses(sessionWindow),
    placeholderData: (prev) => prev,
  });

  // The first character of a search can widen the list to every address, so let
  // React keep the old cards on screen while the new ones mount.
  const query = useDeferredValue(search).trim();
  // Without a search the single-account addresses are noise; a search is a lookup
  // and has to reach them.
  const shown = (overview?.addresses ?? []).filter((address) =>
    query ? address.ip.includes(query) : showAll || address.account_count > 1,
  );
  const total = overview?.address_count ?? 0;

  function emptyMessage() {
    if (query) {
      return live
        ? t("admin.sessions.empty_search", {
            query,
            defaultValue: "No live session comes from an address matching {{query}}.",
          })
        : t("admin.sessions.empty_search_window", {
            query,
            defaultValue: "No login came from an address matching {{query}}.",
          });
    }
    if (total === 0) {
      return live
        ? t("admin.sessions.empty", { defaultValue: "No one is signed in." })
        : t("admin.sessions.empty_window", {
            defaultValue: "No login was recorded in this window.",
          });
    }
    return t("admin.sessions.empty_shared", {
      defaultValue: "No address has more than one account signed in.",
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <WindowSwitch value={sessionWindow} options={SESSION_WINDOWS} onChange={setSessionWindow} />
        <RefreshButton onClick={() => void refetch()} busy={isFetching} />
      </div>

      {overview && <SessionSummary overview={overview} live={live} />}

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">
          {query
            ? t("admin.sessions.count_matching", {
                shown: shown.length,
                total,
                defaultValue: "{{shown}} of {{total}} addresses match",
              })
            : t("admin.sessions.count_shown", {
                shown: shown.length,
                total,
                defaultValue: "Showing {{shown}} of {{total}} addresses",
              })}
          {!query && (
            <button
              type="button"
              onClick={() => setShowAll((prev) => !prev)}
              className="ml-2 text-link underline-offset-2 hover:underline"
            >
              {showAll
                ? t("admin.sessions.show_shared", { defaultValue: "Shared only" })
                : t("admin.sessions.show_all", { defaultValue: "Show every address" })}
            </button>
          )}
        </p>
        <div className="w-full sm:max-w-64">
          <SearchInput
            value={search}
            onValueChange={setSearch}
            aria-label={t("admin.sessions.search", { defaultValue: "Search an address" })}
            placeholder={t("admin.sessions.search", { defaultValue: "Search an address" })}
          />
        </div>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      ) : shown.length === 0 ? (
        <p className="text-sm text-muted-foreground">{emptyMessage()}</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {shown.map((address) => (
            <AddressCard key={address.ip} address={address} live={live} />
          ))}
        </div>
      )}
    </div>
  );
}

function FailedLoginCard({ address }: { address: FailedLoginAddress }) {
  const { t, i18n } = useTranslation();
  const meta = [
    t("admin.sessions.failed_attempts", {
      total: address.attempt_count,
      defaultValue: "{{total}} attempts",
    }),
    address.known_username_count > 0
      ? t("admin.sessions.failed_known", {
          total: address.known_username_count,
          defaultValue: "{{total}} match an account",
        })
      : "",
    formatLastSeen(address.last_attempt_at, i18n.language),
  ].filter(Boolean);

  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <code className="rounded bg-muted px-2 py-1 font-mono text-sm">{address.ip}</code>
          <StatusBadge tone={address.username_count > 1 ? "amber" : "muted"}>
            {t("admin.sessions.failed_usernames", {
              count: address.username_count,
              defaultValue: "{{count}} username",
              defaultValue_other: "{{count}} usernames",
            })}
          </StatusBadge>
        </div>
        <p className="text-xs text-muted-foreground">{meta.join(" · ")}</p>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          {address.usernames.map((tried) => (
            <span key={`${tried.username}-${tried.user_id}`} className="flex items-center gap-1">
              {tried.user_id ? (
                <UserLink id={tried.user_id} name={tried.username} />
              ) : (
                <span className="text-muted-foreground">{tried.username}</span>
              )}
              <span className="text-muted-foreground">({tried.attempt_count})</span>
            </span>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function FailedLoginsTab() {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const [showAll, setShowAll] = useState(false);
  const [failedWindow, setFailedWindow] = useState<SessionWindow>("day");

  const {
    data: overview,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["admin", "session-failed-logins", failedWindow],
    queryFn: () => getAdminSessionFailedLogins(failedWindow),
    placeholderData: (prev) => prev,
  });

  const query = useDeferredValue(search).trim();
  // One username tried repeatedly is someone forgetting a password; the signal
  // is one address working through many names.
  const shown = (overview?.addresses ?? []).filter((address) =>
    query ? address.ip.includes(query) : showAll || address.username_count > 1,
  );
  const total = overview?.address_count ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <WindowSwitch value={failedWindow} options={FAILED_WINDOWS} onChange={setFailedWindow} />
        <RefreshButton onClick={() => void refetch()} busy={isFetching} />
      </div>

      {overview && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <StatCard
            label={t("admin.sessions.failed_stat_attempts", { defaultValue: "Attempts" })}
            value={overview.attempt_count}
          />
          <StatCard
            label={t("admin.sessions.stat_addresses", { defaultValue: "Addresses" })}
            value={overview.address_count}
          />
          <StatCard
            label={t("admin.sessions.failed_stat_sprayed", {
              defaultValue: "Tried many usernames",
            })}
            value={overview.spray_address_count}
          />
        </div>
      )}

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">
          {query
            ? t("admin.sessions.count_matching", {
                shown: shown.length,
                total,
                defaultValue: "{{shown}} of {{total}} addresses match",
              })
            : t("admin.sessions.count_shown", {
                shown: shown.length,
                total,
                defaultValue: "Showing {{shown}} of {{total}} addresses",
              })}
          {!query && (
            <button
              type="button"
              onClick={() => setShowAll((prev) => !prev)}
              className="ml-2 text-link underline-offset-2 hover:underline"
            >
              {showAll
                ? t("admin.sessions.failed_show_sprayed", { defaultValue: "Sprayed only" })
                : t("admin.sessions.failed_show_all", {
                    defaultValue: "Show every failing address",
                  })}
            </button>
          )}
        </p>
        <div className="w-full sm:max-w-64">
          <SearchInput
            value={search}
            onValueChange={setSearch}
            aria-label={t("admin.sessions.search", { defaultValue: "Search an address" })}
            placeholder={t("admin.sessions.search", { defaultValue: "Search an address" })}
          />
        </div>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      ) : shown.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {query
            ? t("admin.sessions.failed_empty_search", {
                query,
                defaultValue: "No failed login came from an address matching {{query}}.",
              })
            : total === 0
              ? t("admin.sessions.failed_empty", {
                  defaultValue: "No failed login in this window.",
                })
              : t("admin.sessions.failed_empty_sprayed", {
                  defaultValue: "No address tried more than one username.",
                })}
        </p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {shown.map((address) => (
            <FailedLoginCard key={address.ip} address={address} />
          ))}
        </div>
      )}
    </div>
  );
}

function SecurityPage() {
  const { t } = useTranslation();
  const { tab } = Route.useSearch();

  return (
    <div className="p-8 space-y-6">
      <PageHeader
        icon={ShieldAlert}
        title={t("admin.nav.security", { defaultValue: "Security" })}
        badge={<BetaBadge />}
      />

      <TabNav active={tab} />

      {tab === "sessions" ? <SessionsTab /> : <FailedLoginsTab />}
    </div>
  );
}
