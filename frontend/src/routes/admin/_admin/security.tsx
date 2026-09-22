import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { RefreshCw, ShieldAlert } from "lucide-react";
import { Fragment, memo, type ReactNode, useDeferredValue, useState } from "react";
import { useTranslation } from "react-i18next";
import { BetaBadge } from "@/components/beta-badge";
import { PageHeader } from "@/components/page-header";
import { SearchInput } from "@/components/search-input";
import { StatCard } from "@/components/stat-card";
import { StatusBadge } from "@/components/status-badge";
import { TeamLink, UserLink } from "@/components/table-cells";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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

const FAILED_WINDOWS: readonly SessionWindow[] = ["day", "all"];

export const Route = createFileRoute("/admin/_admin/security")({
  component: SecurityPage,
  validateSearch: (search: Record<string, unknown>): { tab: SecurityTab } => ({
    tab: TABS.includes(search.tab as SecurityTab) ? (search.tab as SecurityTab) : "sessions",
  }),
});

function WindowBar({
  value,
  options,
  onChange,
  onRefresh,
  busy,
}: {
  value: SessionWindow;
  options: readonly SessionWindow[];
  onChange: (window: SessionWindow) => void;
  onRefresh: () => void;
  busy: boolean;
}) {
  const { t } = useTranslation();
  const labels: Record<SessionWindow, string> = {
    live: t("admin.sessions.window_live", { defaultValue: "Live now" }),
    day: t("admin.sessions.window_day", { defaultValue: "Last 24 hours" }),
    all: t("admin.sessions.window_all", { defaultValue: "Whole event" }),
  };

  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
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
      <Button
        variant="outline"
        size="icon-sm"
        onClick={onRefresh}
        disabled={busy}
        aria-label={t("table.refresh", { defaultValue: "Refresh" })}
      >
        <RefreshCw className={`size-3.5 ${busy ? "animate-spin" : ""}`} />
      </Button>
    </div>
  );
}

function IpChip({ ip }: { ip: string }) {
  return <code className="rounded bg-muted px-2 py-1 font-mono text-sm">{ip}</code>;
}

/** Searchable card grid over addresses, flagged ones only unless widened. */
function AddressList<T extends { ip: string }>({
  addresses,
  total,
  isLoading,
  isFlagged,
  toggleLabels,
  emptyMessage,
  renderCard,
}: {
  addresses: T[];
  total: number;
  isLoading: boolean;
  isFlagged: (address: T) => boolean;
  toggleLabels: { flagged: string; all: string };
  emptyMessage: (query: string) => string;
  renderCard: (address: T) => ReactNode;
}) {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const [showAll, setShowAll] = useState(false);
  const query = useDeferredValue(search).trim();
  const shown = addresses.filter((address) =>
    query ? address.ip.includes(query) : showAll || isFlagged(address),
  );

  return (
    <>
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
              {showAll ? toggleLabels.flagged : toggleLabels.all}
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
        <p className="text-sm text-muted-foreground">{emptyMessage(query)}</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {shown.map((address) => (
            <Fragment key={address.ip}>{renderCard(address)}</Fragment>
          ))}
        </div>
      )}
    </>
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
          <IpChip ip={address.ip} />
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
  const total = overview?.address_count ?? 0;

  function emptyMessage(query: string) {
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
      <WindowBar
        value={sessionWindow}
        options={SESSION_WINDOWS}
        onChange={setSessionWindow}
        onRefresh={() => void refetch()}
        busy={isFetching}
      />
      {overview && <SessionSummary overview={overview} live={live} />}
      <AddressList
        addresses={overview?.addresses ?? []}
        total={total}
        isLoading={isLoading}
        isFlagged={(address) => address.account_count > 1}
        toggleLabels={{
          flagged: t("admin.sessions.show_shared", { defaultValue: "Shared only" }),
          all: t("admin.sessions.show_all", { defaultValue: "Show every address" }),
        }}
        emptyMessage={emptyMessage}
        renderCard={(address) => <AddressCard address={address} live={live} />}
      />
    </div>
  );
}

const FailedLoginCard = memo(function FailedLoginCard({
  address,
}: {
  address: FailedLoginAddress;
}) {
  const { t, i18n } = useTranslation();
  const meta = [
    t("admin.sessions.failed_attempts", {
      total: address.attempt_count,
      defaultValue: "{{total}} attempts",
    }),
    address.known_username_count > 0
      ? t("admin.sessions.failed_known", {
          count: address.known_username_count,
          defaultValue: "{{count}} matches an account",
          defaultValue_other: "{{count}} match an account",
        })
      : "",
    formatLastSeen(address.last_attempt_at, i18n.language),
  ].filter(Boolean);
  const hidden = address.username_count - new Set(address.usernames.map((u) => u.username)).size;

  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <IpChip ip={address.ip} />
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
          {hidden > 0 && (
            <span className="text-muted-foreground">
              {t("admin.sessions.failed_more", { hidden, defaultValue: "+{{hidden}} more" })}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
});

function FailedLoginsTab() {
  const { t } = useTranslation();
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
  const total = overview?.address_count ?? 0;

  function emptyMessage(query: string) {
    if (query) {
      return t("admin.sessions.failed_empty_search", {
        query,
        defaultValue: "No failed login came from an address matching {{query}}.",
      });
    }
    if (total === 0) {
      return t("admin.sessions.failed_empty", { defaultValue: "No failed login in this window." });
    }
    return t("admin.sessions.failed_empty_sprayed", {
      defaultValue: "No address tried more than one username.",
    });
  }

  return (
    <div className="space-y-6">
      <WindowBar
        value={failedWindow}
        options={FAILED_WINDOWS}
        onChange={setFailedWindow}
        onRefresh={() => void refetch()}
        busy={isFetching}
      />
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
      <AddressList
        addresses={overview?.addresses ?? []}
        total={total}
        isLoading={isLoading}
        isFlagged={(address) => address.username_count > 1}
        toggleLabels={{
          flagged: t("admin.sessions.failed_show_sprayed", { defaultValue: "Many usernames only" }),
          all: t("admin.sessions.failed_show_all", { defaultValue: "Show every failing address" }),
        }}
        emptyMessage={emptyMessage}
        renderCard={(address) => <FailedLoginCard address={address} />}
      />
    </div>
  );
}

function SecurityPage() {
  const { t } = useTranslation();
  const { tab } = Route.useSearch();
  const navigate = Route.useNavigate();

  return (
    <div className="p-8 space-y-6">
      <PageHeader
        icon={ShieldAlert}
        title={t("admin.nav.security", { defaultValue: "Security" })}
        badge={<BetaBadge />}
      />

      <Tabs
        value={tab}
        onValueChange={(value: SecurityTab) => void navigate({ search: { tab: value } })}
        className="gap-6"
      >
        <TabsList variant="line">
          <TabsTrigger value="sessions">
            {t("admin.security.tab_sessions", { defaultValue: "Sessions" })}
          </TabsTrigger>
          <TabsTrigger value="failed-logins">
            {t("admin.security.tab_failed_logins", { defaultValue: "Failed logins" })}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="sessions">
          <SessionsTab />
        </TabsContent>
        <TabsContent value="failed-logins">
          <FailedLoginsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
