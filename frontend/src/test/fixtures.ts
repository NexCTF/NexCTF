import type {
  ApiToken,
  FailedLoginAddress,
  FailedLoginOverview,
  FailedLoginUsername,
  MyTeam,
  PaginatedResponse,
  PublicChallenge,
  PublicChallengeDetail,
  PublicInfo,
  PublicQuestion,
  Scoreboard,
  SessionOverview,
  SharedAddress,
  SharedAddressAccount,
  User,
  UserSession,
} from "@/lib/api";
import { DEFAULT_BRANDING } from "@/lib/branding";

/** `/info` payload with everything off — override what a test cares about. */
export function publicInfo(overrides: Partial<PublicInfo> = {}): PublicInfo {
  return {
    branding: DEFAULT_BRANDING,
    competition: {
      description: "",
      start_time: "2026-01-01T00:00:00Z",
      end_time: "2026-01-02T00:00:00Z",
      freeze_time: "2026-01-02T00:00:00Z",
      allow_registration: true,
      allow_team_creation: true,
      require_email: false,
      allow_team_changes: true,
      allow_user_customization: false,
      allow_team_customization: false,
      enable_challenge_feedback: false,
      team_size: 4,
    },
    oauth_providers: [],
    captcha: { enabled: false },
    links: [],
    ...overrides,
  };
}

/** Same as `publicInfo`, with only the competition block patched. */
export function publicInfoWith(competition: Partial<PublicInfo["competition"]>): PublicInfo {
  return publicInfo({ competition: { ...publicInfo().competition, ...competition } });
}

export function user(overrides: Partial<User> = {}): User {
  return {
    id: "u1",
    username: "player",
    email: null,
    role: "user",
    is_active: true,
    team_id: null,
    team_name: null,
    totp_enabled: false,
    has_password: true,
    links: [],
    ...overrides,
  };
}

export function paginated<T>(items: T[]): PaginatedResponse<T> {
  return {
    status: "SUCCESS",
    message: "",
    error_code: null,
    data: items,
    pagination: {
      total_count: items.length,
      items_per_page: 50,
      page: 1,
      has_more: false,
      pages: 1,
    },
    pagination_type: "offset",
    filter_attributes: {},
    search_columns: [],
    order_columns: [],
  };
}

export function challenge(overrides: Partial<PublicChallenge> = {}): PublicChallenge {
  return {
    id: "c1",
    title: "Baby RSA",
    category: "crypto",
    question_count: 2,
    solved_count: 0,
    tags: [],
    ...overrides,
  };
}

export function question(overrides: Partial<PublicQuestion> = {}): PublicQuestion {
  return {
    id: "q1",
    label: "What is the flag?",
    description: null,
    is_locked: false,
    points: 100,
    malus: null,
    input_type: "input",
    is_solved: false,
    files: [],
    hints: [],
    tags: [],
    options: null,
    multi_select: false,
    ...overrides,
  };
}

export function challengeDetail(
  overrides: Partial<PublicChallengeDetail> = {},
): PublicChallengeDetail {
  return {
    ...challenge(),
    challenge_type: "static",
    description: null,
    writeup: null,
    sequential: false,
    question_count: 1,
    questions: [question()],
    completed: false,
    my_feedback: null,
    score_adjustments: [],
    ...overrides,
  };
}

export function team(overrides: Partial<MyTeam> = {}): MyTeam {
  return {
    id: "t1",
    name: "Alpha",
    country: null,
    bracket: null,
    links: [],
    members: [{ id: "u1", username: "player", links: [], custom_fields: [] }],
    member_count: 1,
    challenge_stats: [],
    custom_fields: [],
    rank: 1,
    score: 100,
    team_count: 3,
    invite_code: "INVITE123",
    ...overrides,
  };
}

export function scoreboard(overrides: Partial<Scoreboard> = {}): Scoreboard {
  return {
    entries: [
      {
        rank: 1,
        team_id: "t1",
        team_name: "Alpha",
        team_bracket: null,
        total: 300,
        custom_fields: {},
      },
      {
        rank: 2,
        team_id: "t2",
        team_name: "Beta",
        team_bracket: null,
        total: 100,
        custom_fields: {},
      },
    ],
    computed_at: "2026-01-01T12:00:00Z",
    brackets: [],
    custom_fields: [],
    ...overrides,
  };
}

export function apiToken(overrides: Partial<ApiToken> = {}): ApiToken {
  return {
    id: "tok1",
    name: "CI",
    created_at: "2026-01-01T00:00:00Z",
    expires_at: null,
    last_used_at: null,
    scopes: ["write:challenge", "read:scoreboard"],
    ...overrides,
  };
}

export function userSession(overrides: Partial<UserSession> = {}): UserSession {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    ip: "203.0.113.7",
    last_ip: "203.0.113.7",
    user_agent: "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    last_seen_at: new Date().toISOString(),
    current: false,
    ...overrides,
  };
}

export function sharedAddressAccount(
  overrides: Partial<SharedAddressAccount> = {},
): SharedAddressAccount {
  return {
    user_id: "22222222-2222-4222-8222-222222222222",
    username: "alice",
    team_id: null,
    team_name: null,
    session_count: 1,
    last_seen_at: new Date().toISOString(),
    user_agent: "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    opened_here: true,
    ...overrides,
  };
}

export function sharedAddress(overrides: Partial<SharedAddress> = {}): SharedAddress {
  const accounts = overrides.accounts ?? [
    sharedAddressAccount(),
    sharedAddressAccount({
      user_id: "33333333-3333-4333-8333-333333333333",
      username: "bob",
    }),
  ];
  return {
    ip: "203.0.113.7",
    account_count: accounts.length,
    session_count: accounts.reduce((total, a) => total + a.session_count, 0),
    same_team: false,
    team_count: new Set(accounts.map((a) => a.team_id).filter(Boolean)).size,
    last_seen_at: new Date().toISOString(),
    ...overrides,
    accounts,
  };
}

export function sessionOverview(overrides: Partial<SessionOverview> = {}): SessionOverview {
  const addresses = overrides.addresses ?? [sharedAddress()];
  return {
    // Totals are server-side aggregates over sessions, not sums of these rows:
    // tests that assert them pass their own.
    session_count: 0,
    account_count: 0,
    address_count: addresses.length,
    shared_address_count: 0,
    cross_team_address_count: 0,
    ...overrides,
    addresses,
  };
}

export function failedLoginUsername(
  overrides: Partial<FailedLoginUsername> = {},
): FailedLoginUsername {
  return {
    username: "alice",
    user_id: null,
    attempt_count: 1,
    last_attempt_at: new Date().toISOString(),
    ...overrides,
  };
}

export function failedLoginAddress(
  overrides: Partial<FailedLoginAddress> = {},
): FailedLoginAddress {
  const usernames = overrides.usernames ?? [
    failedLoginUsername(),
    failedLoginUsername({ username: "bob" }),
  ];
  return {
    ip: "203.0.113.9",
    attempt_count: usernames.reduce((total, tried) => total + tried.attempt_count, 0),
    username_count: new Set(usernames.map((tried) => tried.username)).size,
    known_username_count: usernames.filter((tried) => tried.user_id).length,
    last_attempt_at: new Date().toISOString(),
    ...overrides,
    usernames,
  };
}

export function failedLoginOverview(
  overrides: Partial<FailedLoginOverview> = {},
): FailedLoginOverview {
  const addresses = overrides.addresses ?? [failedLoginAddress()];
  return {
    // Totals are server-side aggregates, not sums of these rows.
    attempt_count: 0,
    address_count: addresses.length,
    spray_address_count: 0,
    ...overrides,
    addresses,
  };
}
