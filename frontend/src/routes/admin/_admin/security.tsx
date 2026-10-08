import { useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ShieldAlert } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { BetaBadge } from "@/components/beta-badge";
import {
  ClientCategoryBadge,
  ClientSourceBadge,
  UserAgentText,
  useClientLabels,
} from "@/components/client-badges";
import { type Column, DataTable, useTableState } from "@/components/data-table";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { StatusBadge } from "@/components/status-badge";
import { LastSeenCell, TeamLink, UserLink } from "@/components/table-cells";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  type ClientSighting,
  type FailedLoginAddress,
  getAdminSessionAddresses,
  getAdminSessionClients,
  getAdminSessionClientsSummary,
  getAdminSessionFailedLogins,
  SESSION_WINDOWS,
  type SessionOverview,
  type SessionWindow,
  type SharedAddress,
  type SharedAddressAccount,
} from "@/lib/api";
import { type ClientPageSpec, clientPage } from "@/lib/client-page";
import { describeDevice, formatLastSeen } from "@/lib/session";

const TABS = ["sessions", "failed-logins", "clients"] as const;

type SecurityTab = (typeof TABS)[number];

const PAST_WINDOWS: readonly SessionWindow[] = ["day", "all"];

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
      className="flex flex-wrap gap-1"
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

/** A time window and the table it feeds: a new window goes back to page 1. */
function useWindowedTable(initial: SessionWindow) {
  const [sessionWindow, setSessionWindow] = useState(initial);
  const table = useTableState();
  const setWindow = (next: SessionWindow) => {
    setSessionWindow(next);
    table.setPage(1);
  };
  return { sessionWindow, setWindow, table };
}

function IpChip({ ip }: { ip: string }) {
  return <code className="rounded bg-muted px-2 py-1 font-mono text-sm">{ip}</code>;
}

function TeamBadge({ address }: { address: SharedAddress }) {
  const { t } = useTranslation();
  if (address.account_count < 2) return null;
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

function AddressAccount({ account, live }: { account: SharedAddressAccount; live: boolean }) {
  const { t, i18n } = useTranslation();
  const { browser, os } = describeDevice(account.user_agent);
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
    volume,
    formatLastSeen(account.last_seen_at, i18n.language),
  ].filter(Boolean);

  return (
    <span className="inline-flex items-center gap-1" title={meta.join(" · ")}>
      <UserLink id={account.user_id} name={account.username} />
      {(account.team_id || account.team_name) && (
        <TeamLink id={account.team_id} name={account.team_name} />
      )}
      {!account.opened_here && (
        <StatusBadge tone="amber">
          {t("admin.sessions.moved_here", { defaultValue: "Moved here" })}
        </StatusBadge>
      )}
    </span>
  );
}

const ADDRESS_PAGE: ClientPageSpec<SharedAddress> = {
  searchText: (address) =>
    [address.ip, ...address.accounts.flatMap((a) => [a.username, a.team_name ?? ""])].join(" "),
  filters: {
    account_count: {
      options: ["shared", "single"],
      matches: (address, value) => address.account_count > 1 === (value === "shared"),
    },
    team_count: {
      options: ["cross_team", "same_team"],
      matches: (address, value) =>
        value === "cross_team"
          ? address.team_count > 1
          : address.same_team && address.account_count > 1,
    },
  },
  sorters: {
    ip: (address) => address.ip,
    account_count: (address) => address.account_count,
    team_count: (address) => address.team_count,
    session_count: (address) => address.session_count,
    last_seen_at: (address) => address.last_seen_at,
  },
  defaultSort: (a, b) =>
    b.account_count - a.account_count || b.last_seen_at.localeCompare(a.last_seen_at),
};

function useAddressColumns(live: boolean): Column<SharedAddress>[] {
  const { t } = useTranslation();
  return [
    {
      key: "ip",
      header: t("admin.sessions.col_address", { defaultValue: "Address" }),
      cell: (address) => <IpChip ip={address.ip} />,
    },
    {
      key: "account_count",
      header: t("admin.sessions.col_accounts", { defaultValue: "Accounts" }),
      filterOptions: {
        shared: t("admin.sessions.filter_shared", { defaultValue: "Shared" }),
        single: t("admin.sessions.filter_single", { defaultValue: "Single account" }),
      },
      cell: (address) => (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          {address.accounts.map((account) => (
            <AddressAccount key={account.user_id} account={account} live={live} />
          ))}
        </div>
      ),
    },
    {
      key: "team_count",
      header: t("admin.sessions.col_teams", { defaultValue: "Teams" }),
      filterOptions: {
        cross_team: t("admin.sessions.cross_team", { defaultValue: "Different teams" }),
        same_team: t("admin.sessions.same_team", { defaultValue: "Same team" }),
      },
      cell: (address) => <TeamBadge address={address} />,
    },
    {
      key: "session_count",
      header: live
        ? t("admin.sessions.stat_sessions", { defaultValue: "Live sessions" })
        : t("admin.sessions.stat_logins", { defaultValue: "Logins" }),
      className: "tabular-nums",
    },
    {
      key: "last_seen_at",
      header: t("admin.clients.col_last_seen", { defaultValue: "Last seen" }),
      cell: (address) => <LastSeenCell value={address.last_seen_at} />,
    },
  ];
}

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
  const { sessionWindow, setWindow, table } = useWindowedTable("live");
  const live = sessionWindow === "live";
  const columns = useAddressColumns(live);

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
  const response = useMemo(
    () => overview && clientPage(overview.addresses, table.state, ADDRESS_PAGE),
    [overview, table.state],
  );

  return (
    <div className="space-y-6">
      <WindowBar value={sessionWindow} options={SESSION_WINDOWS} onChange={setWindow} />
      {overview && <SessionSummary overview={overview} live={live} />}
      <DataTable
        columns={columns}
        response={response}
        table={table}
        isLoading={isLoading}
        isFetching={isFetching}
        rowKey={(address) => address.ip}
        onRefresh={() => void refetch()}
      />
    </div>
  );
}

function TriedUsernames({ address }: { address: FailedLoginAddress }) {
  const { t } = useTranslation();
  const hidden = address.username_count - new Set(address.usernames.map((u) => u.username)).size;
  return (
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
  );
}

const FAILED_LOGIN_PAGE: ClientPageSpec<FailedLoginAddress> = {
  searchText: (address) => [address.ip, ...address.usernames.map((u) => u.username)].join(" "),
  filters: {
    username_count: {
      options: ["many", "one"],
      matches: (address, value) => address.username_count > 1 === (value === "many"),
    },
    known_username_count: {
      options: ["known", "unknown"],
      matches: (address, value) => address.known_username_count > 0 === (value === "known"),
    },
  },
  sorters: {
    ip: (address) => address.ip,
    attempt_count: (address) => address.attempt_count,
    username_count: (address) => address.username_count,
    known_username_count: (address) => address.known_username_count,
    last_attempt_at: (address) => address.last_attempt_at,
  },
  defaultSort: (a, b) => b.username_count - a.username_count || b.attempt_count - a.attempt_count,
};

function useFailedLoginColumns(): Column<FailedLoginAddress>[] {
  const { t } = useTranslation();
  return [
    {
      key: "ip",
      header: t("admin.sessions.col_address", { defaultValue: "Address" }),
      cell: (address) => <IpChip ip={address.ip} />,
    },
    {
      key: "attempt_count",
      header: t("admin.sessions.failed_stat_attempts", { defaultValue: "Attempts" }),
      className: "tabular-nums",
    },
    {
      key: "username_count",
      header: t("admin.sessions.col_usernames", { defaultValue: "Usernames" }),
      filterOptions: {
        many: t("admin.sessions.filter_many", { defaultValue: "Several" }),
        one: t("admin.sessions.filter_one", { defaultValue: "One" }),
      },
      cell: (address) => (
        <StatusBadge tone={address.username_count > 1 ? "amber" : "muted"}>
          {address.username_count}
        </StatusBadge>
      ),
    },
    {
      key: "known_username_count",
      header: t("admin.sessions.col_known", { defaultValue: "Known accounts" }),
      className: "tabular-nums",
      filterOptions: {
        known: t("admin.sessions.filter_known", { defaultValue: "Matches an account" }),
        unknown: t("admin.sessions.filter_unknown", { defaultValue: "No match" }),
      },
    },
    {
      key: "usernames",
      header: t("admin.sessions.col_tried", { defaultValue: "Tried" }),
      sortable: false,
      cell: (address) => <TriedUsernames address={address} />,
    },
    {
      key: "last_attempt_at",
      header: t("admin.sessions.col_last_attempt", { defaultValue: "Last attempt" }),
      cell: (address) => <LastSeenCell value={address.last_attempt_at} />,
    },
  ];
}

function FailedLoginsTab() {
  const { t } = useTranslation();
  const columns = useFailedLoginColumns();
  const { sessionWindow: failedWindow, setWindow, table } = useWindowedTable("day");

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
  const response = useMemo(
    () => overview && clientPage(overview.addresses, table.state, FAILED_LOGIN_PAGE),
    [overview, table.state],
  );

  return (
    <div className="space-y-6">
      <WindowBar value={failedWindow} options={PAST_WINDOWS} onChange={setWindow} />
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
      <DataTable
        columns={columns}
        response={response}
        table={table}
        isLoading={isLoading}
        isFetching={isFetching}
        rowKey={(address) => address.ip}
        onRefresh={() => void refetch()}
      />
    </div>
  );
}

function ClientSummaryCards({ sessionWindow }: { sessionWindow: SessionWindow }) {
  const { t } = useTranslation();
  const { data: summary } = useQuery({
    queryKey: ["admin", "session-clients-summary", sessionWindow],
    queryFn: () => getAdminSessionClientsSummary(sessionWindow),
    placeholderData: (prev) => prev,
  });
  if (!summary) return null;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      <StatCard
        label={t("admin.clients.stat_clients", { defaultValue: "Clients" })}
        value={summary.client_count}
      />
      <StatCard
        label={t("admin.clients.stat_accounts", { defaultValue: "Accounts seen" })}
        value={summary.account_count}
      />
      <StatCard
        label={t("admin.clients.stat_ai_accounts", { defaultValue: "Accounts on AI clients" })}
        value={summary.ai_account_count}
      />
      <StatCard
        label={t("admin.clients.stat_automation_accounts", {
          defaultValue: "Accounts on automation",
        })}
        value={summary.automation_account_count}
      />
      <StatCard
        label={t("admin.clients.stat_token_accounts", {
          defaultValue: "Accounts using tokens",
        })}
        value={summary.token_account_count}
      />
    </div>
  );
}

function useClientColumns(): Column<ClientSighting>[] {
  const { t } = useTranslation();
  const labels = useClientLabels();
  return [
    {
      key: "user__username",
      header: t("table.col_username", { defaultValue: "Username" }),
      cell: (row) => <UserLink id={row.user_id} name={row.username} />,
    },
    {
      key: "team__name",
      header: t("table.col_team", { defaultValue: "Team" }),
      cell: (row) => <TeamLink id={row.team_id} name={row.team_name} />,
    },
    {
      key: "category",
      header: t("admin.clients.col_category", { defaultValue: "Category" }),
      filterOptions: labels.category,
      cell: (row) => <ClientCategoryBadge category={row.category} />,
    },
    {
      key: "source",
      header: t("admin.clients.col_source", { defaultValue: "Source" }),
      filterOptions: labels.source,
      cell: (row) => <ClientSourceBadge source={row.source} tokenName={row.token_name} />,
    },
    {
      key: "user_agent",
      header: t("admin.clients.col_user_agent", { defaultValue: "User-agent" }),
      cell: (row) => <UserAgentText userAgent={row.user_agent} truncate />,
    },
    {
      key: "last_seen_at",
      header: t("admin.clients.col_last_seen", { defaultValue: "Last seen" }),
      cell: (row) => <LastSeenCell value={row.last_seen_at} />,
    },
  ];
}

function ClientsTab() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const columns = useClientColumns();
  const { sessionWindow: clientWindow, setWindow, table } = useWindowedTable("day");

  const {
    data: response,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["admin", "session-clients", clientWindow, table.queryString],
    queryFn: () => getAdminSessionClients(clientWindow, table.queryString),
    placeholderData: (prev) => prev,
  });

  return (
    <div className="space-y-6">
      <WindowBar value={clientWindow} options={PAST_WINDOWS} onChange={setWindow} />
      <ClientSummaryCards sessionWindow={clientWindow} />
      <p className="text-xs text-muted-foreground">
        {t("admin.clients.hint", {
          defaultValue:
            "User-agents are sent by the client and easy to fake: a match is a hint, its absence proves nothing. Patterns are set under Beta settings.",
        })}
      </p>
      <DataTable
        columns={columns}
        response={response}
        table={table}
        isLoading={isLoading}
        isFetching={isFetching}
        rowKey={(row) => row.id}
        onRefresh={() => void refetch()}
        onRowClick={(row) =>
          void navigate({ to: "/admin/users/$userId", params: { userId: row.user_id } })
        }
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
          <TabsTrigger value="clients">
            {t("admin.security.tab_clients", { defaultValue: "Clients" })}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="sessions">
          <SessionsTab />
        </TabsContent>
        <TabsContent value="failed-logins">
          <FailedLoginsTab />
        </TabsContent>
        <TabsContent value="clients">
          <ClientsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
