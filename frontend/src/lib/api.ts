const BASE = "/api/v1";

// ---------------------------------------------------------------------------
// Response types matching fastapi_toolsets.schemas
// ---------------------------------------------------------------------------

interface ApiResponse<T> {
  status: "SUCCESS" | "FAIL";
  message: string;
  error_code: string | null;
  data: T | null;
}

export interface PaginatedResponse<T> {
  status: "SUCCESS" | "FAIL";
  message: string;
  error_code: string | null;
  data: T[];
  pagination: {
    total_count: number;
    items_per_page: number;
    page: number;
    has_more: boolean;
    pages: number;
  };
  pagination_type: string;
  filter_attributes: Record<string, unknown[]>;
  search_columns: string[];
  order_columns: string[];
}

export interface CursorPaginatedResponse<T> {
  data: T[];
  pagination: {
    next_cursor: string | null;
    prev_cursor: string | null;
    has_more: boolean;
  };
  pagination_type: "cursor";
  filter_attributes: Record<string, unknown[]>;
  search_columns: string[];
  order_columns: string[];
}

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

async function throwIfNotOk(res: Response): Promise<void> {
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(
      res.status,
      body?.message ?? res.statusText,
      body?.description ?? null,
      body?.error_code ?? null,
    );
  }
}

async function rawRequest(path: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  await throwIfNotOk(res);
  return res;
}

/** For endpoints returning `Response[T]` — unwraps the `data` field. */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await rawRequest(path, init);
  if (res.status === 204) return undefined as T;
  const json: ApiResponse<T> = await res.json();
  return json.data as T;
}

/** For endpoints returning `PaginatedResponse[T]` — returns as-is. */
async function requestPaginated<T>(
  path: string,
  init?: RequestInit,
): Promise<PaginatedResponse<T>> {
  const res = await rawRequest(path, init);
  return res.json();
}

/** Generic GET helper for dynamic defaults and other ad-hoc fetches. */
export async function apiGet<T>(path: string): Promise<T> {
  return request<T>(path);
}

export class ApiError extends Error {
  status: number;
  /** Short error message (maps to fastapi-toolsets `message` field). */
  message: string;
  /** Extended description, if provided by the backend. */
  description: string | null;
  /** Machine-readable error code (e.g. "AUTH-TOTP-REQUIRED"). */
  errCode: string | null;

  constructor(
    status: number,
    message: string,
    description: string | null = null,
    errCode: string | null = null,
  ) {
    super(message);
    this.status = status;
    this.message = message;
    this.description = description;
    this.errCode = errCode;
  }
}

/** Extract a human-readable message from an error, falling back to a provided string. */
export function apiErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.description ?? err.message;
  return fallback;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface Link {
  label: string;
  url: string;
}

export interface User {
  id: string;
  username: string;
  email: string | null;
  role: string;
  is_active: boolean;
  team_id: string | null;
  team_name: string | null;
  totp_enabled: boolean;
  links: Link[];
}

export interface OAuthProvider {
  slug: string;
  name: string;
  icon_url: string | null;
}

export async function login(
  username: string,
  password: string,
  totpCode?: string,
  captchaToken?: string,
): Promise<void> {
  const body = new URLSearchParams({ username, password });
  if (totpCode) body.set("totp_code", totpCode);
  if (captchaToken) body.set("cap_token", captchaToken);
  const res = await fetch(`${BASE}/auth/token`, {
    method: "POST",
    credentials: "include",
    body,
  });
  await throwIfNotOk(res);
}

export async function logout(): Promise<void> {
  await rawRequest("/auth/logout", { method: "POST" });
}

export async function register(data: {
  username: string;
  password: string;
  email?: string;
  captchaToken?: string;
}): Promise<void> {
  await rawRequest("/auth/register", {
    method: "POST",
    body: JSON.stringify({
      username: data.username,
      password: data.password,
      email: data.email ?? null,
      cap_token: data.captchaToken ?? null,
    }),
  });
}

// ---------------------------------------------------------------------------
// Info (tiered public / auth / admin)
// ---------------------------------------------------------------------------

export interface BrandingInfo {
  name: string;
  logo_url: string;
  favicon_url: string;
  primary_color: string;
}

export interface CompetitionInfo {
  description: string;
  start_time: string;
  end_time: string;
  freeze_time: string;
  allow_registration: boolean;
  allow_team_creation: boolean;
  team_size: number;
}

export interface CaptchaInfo {
  enabled: boolean;
  widget_endpoint: string;
}

export interface PublicInfo {
  branding: BrandingInfo;
  competition: CompetitionInfo;
  oauth_providers: OAuthProvider[];
  captcha: CaptchaInfo;
}

export interface AdminStats {
  users: number;
  teams: number;
  challenges: number;
  submissions: number;
  correct_submissions: number;
  hint_unlocks: number;
  hint_cost_spent: number;
}

export async function getPublicInfo(): Promise<PublicInfo> {
  return request<PublicInfo>("/info");
}

export async function getMe(): Promise<User> {
  return request<User>("/info/me");
}

export async function getAdminStats(): Promise<AdminStats> {
  return request<AdminStats>("/info/admin");
}

// ---------------------------------------------------------------------------
// Current user — /me/*
// ---------------------------------------------------------------------------

export interface ApiToken {
  id: string;
  name: string | null;
  created_at: string;
  expires_at: string | null;
  /** Only present immediately after creation */
  token?: string;
}

export async function getMyTokens(): Promise<PaginatedResponse<ApiToken>> {
  return requestPaginated<ApiToken>("/me/tokens");
}

export async function createMyToken(name: string): Promise<ApiToken> {
  return request<ApiToken>("/me/tokens", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function deleteMyToken(id: string): Promise<void> {
  await rawRequest(`/me/tokens/${id}`, { method: "DELETE" });
}

export interface TotpSetupData {
  provisioning_uri: string;
}

export async function totpSetup(): Promise<TotpSetupData> {
  return request<TotpSetupData>("/me/totp/setup", { method: "POST" });
}

export async function totpEnable(code: string): Promise<void> {
  await rawRequest("/me/totp/enable", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

export interface OAuthAccount {
  id: string;
  provider_slug: string;
  provider_name: string;
  provider_icon_url: string | null;
}

export async function getMyOAuthAccounts(): Promise<OAuthAccount[]> {
  return request<OAuthAccount[]>("/me/oauth");
}

export async function deleteMyOAuthAccount(id: string): Promise<void> {
  await rawRequest(`/me/oauth/${id}`, { method: "DELETE" });
}

export async function totpDisable(code: string): Promise<void> {
  await rawRequest("/me/totp/disable", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

// ---------------------------------------------------------------------------
// Team — /me/team
// ---------------------------------------------------------------------------

export interface TeamChallengeStats {
  challenge_id: string;
  challenge_title: string;
  question_count: number;
  solved_question_count: number;
  is_solved: boolean;
  attempt_count: number;
  points_earned: number;
  first_solve_at: string | null;
  last_solve_at: string | null;
}

export interface MyTeamMember {
  id: string;
  username: string;
}

export interface MyTeam {
  id: string;
  name: string;
  country: string | null;
  members: MyTeamMember[];
  challenge_stats: TeamChallengeStats[];
  invite_code: string | null;
}

export async function getMyTeam(): Promise<MyTeam | null> {
  return request<MyTeam | null>("/me/team");
}

export async function createTeam(name: string): Promise<MyTeam> {
  return request<MyTeam>("/me/team", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function joinTeam(code: string): Promise<MyTeam> {
  return request<MyTeam>("/me/team/join", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

export async function leaveTeam(): Promise<void> {
  await rawRequest("/me/team/leave", { method: "POST" });
}

export async function rotateInviteCode(): Promise<string> {
  return request<string>("/me/team/invite-code", { method: "POST" });
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

export interface ConfigItem {
  key: string;
  type: "string" | "int" | "float" | "bool" | "choice" | "datetime" | "color" | "url" | "text";
  value: string | number | boolean;
  default: string;
  label: string;
  description: string;
  choices: string[];
  category: string;
  category_label: string;
  category_icon: string | null;
  category_section: string;
  is_plugin_category: boolean;
}

export async function getConfig(): Promise<ConfigItem[]> {
  return request<ConfigItem[]>("/admin/config");
}

export async function updateConfig(items: Record<string, string>): Promise<ConfigItem[]> {
  return request<ConfigItem[]>("/admin/config", {
    method: "PUT",
    body: JSON.stringify({ items }),
  });
}

// ---------------------------------------------------------------------------
// Admin – Users
// ---------------------------------------------------------------------------

export async function getAdminUsers(queryString: string): Promise<PaginatedResponse<User>> {
  return requestPaginated<User>(`/admin/user?${queryString}`);
}

export interface CustomFieldDefinition {
  id: string;
  name: string;
  label: string;
  field_type: "string" | "integer" | "boolean" | "url";
  target: "user" | "team";
  is_required: boolean;
  is_public: boolean;
}

export interface CustomFieldValue {
  id: string;
  definition: CustomFieldDefinition;
  user_id: string | null;
  team_id: string | null;
  value: string | null;
}

export interface AdminUserDetail extends User {
  last_login_ip: string | null;
  last_login_at: string | null;
  custom_field_values: CustomFieldValue[];
}

export async function getAdminUser(userId: string): Promise<AdminUserDetail> {
  return request<AdminUserDetail>(`/admin/user/${userId}`);
}

export async function updateAdminUser(
  userId: string,
  data: {
    username?: string;
    email?: string | null;
    is_active?: boolean;
    role?: string;
    team_id?: string | null;
    links?: Link[];
  },
): Promise<User> {
  return request<User>(`/admin/user/${userId}`, {
    method: "PUT",
    body: JSON.stringify({ id: userId, ...data }),
  });
}

export async function adminResetUserTotp(userId: string): Promise<void> {
  await rawRequest(`/admin/user/${userId}/totp/reset`, { method: "POST" });
}

export async function adminCreatePasswordResetToken(userId: string): Promise<string> {
  return request<string>(`/admin/user/${userId}/password-reset-token`, { method: "POST" });
}

export async function resetPassword(token: string, newPassword: string): Promise<void> {
  await rawRequest("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, new_password: newPassword }),
  });
}

// ---------------------------------------------------------------------------
// Admin – Custom Fields
// ---------------------------------------------------------------------------

export async function getAdminCustomFields(
  queryString: string,
): Promise<PaginatedResponse<CustomFieldDefinition>> {
  return requestPaginated<CustomFieldDefinition>(`/admin/custom-field?${queryString}`);
}

export async function createAdminCustomField(
  data: Omit<CustomFieldDefinition, "id">,
): Promise<CustomFieldDefinition> {
  return request<CustomFieldDefinition>("/admin/custom-field", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAdminCustomField(
  id: string,
  data: Partial<Omit<CustomFieldDefinition, "id" | "target">>,
): Promise<CustomFieldDefinition> {
  return request<CustomFieldDefinition>(`/admin/custom-field/${id}`, {
    method: "PUT",
    body: JSON.stringify({ id, ...data }),
  });
}

export async function deleteAdminCustomField(id: string): Promise<void> {
  await rawRequest(`/admin/custom-field/${id}`, { method: "DELETE" });
}

export async function setAdminCustomFieldValue(data: {
  definition_id: string;
  user_id?: string;
  team_id?: string;
  value: string | null;
}): Promise<CustomFieldValue> {
  return request<CustomFieldValue>("/admin/custom-field-value", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteAdminCustomFieldValue(id: string): Promise<void> {
  await rawRequest(`/admin/custom-field-value/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Admin – Teams
// ---------------------------------------------------------------------------

export interface Team {
  id: string;
  name: string;
  country: string | null;
  links: Link[];
}

export interface TeamMember {
  id: string;
  username: string;
  email: string | null;
  role: string;
  is_active: boolean;
}

export interface TeamDetail extends Team {
  users: TeamMember[];
  custom_field_values: CustomFieldValue[];
}

export async function updateAdminTeam(
  teamId: string,
  data: { name?: string; country?: string | null; links?: Link[] },
): Promise<Team> {
  return request<Team>(`/admin/team/${teamId}`, {
    method: "PUT",
    body: JSON.stringify({ id: teamId, ...data }),
  });
}

export interface AdminSubmission {
  id: string;
  team_id: string;
  question_id: string;
  answer: string;
  is_correct: boolean;
  points_earned: number;
  wrong_count_before: number;
  created_at: string;
  team_name: string | null;
  question_label: string | null;
  question_challenge_title: string | null;
}

export async function getAdminTeams(queryString: string): Promise<PaginatedResponse<Team>> {
  return requestPaginated<Team>(`/admin/team?${queryString}`);
}

export async function getAdminTeamDetail(teamId: string): Promise<TeamDetail> {
  return request<TeamDetail>(`/admin/team/${teamId}/detail`);
}

export async function getAdminSubmissions(
  queryString: string,
): Promise<PaginatedResponse<AdminSubmission>> {
  return requestPaginated<AdminSubmission>(`/admin/submission?${queryString}`);
}

export async function deleteAdminSubmission(id: string): Promise<void> {
  await rawRequest(`/admin/submission/${id}`, { method: "DELETE" });
}

export async function getAdminTeamSubmissions(
  teamId: string,
  queryString: string,
): Promise<PaginatedResponse<AdminSubmission>> {
  return requestPaginated<AdminSubmission>(`/admin/team/${teamId}/submissions?${queryString}`);
}

export async function searchAdminTeamsCursor(
  search: string,
  cursor: string | null,
  perPage = 20,
): Promise<CursorPaginatedResponse<Team>> {
  const params = new URLSearchParams();
  if (search) params.set("search", search);
  if (cursor) params.set("cursor", cursor);
  params.set("items_per_page", perPage.toString());
  params.set("pagination_type", "cursor");
  const res = await rawRequest(`/admin/team?${params}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Admin – Notifications
// ---------------------------------------------------------------------------

export interface AdminNotification {
  id: string;
  title: string;
  is_broadcast: boolean;
  created_by_id: string;
  created_by_username: string | null;
}

export interface AdminNotificationCreate {
  title: string;
  content: string;
  is_broadcast: boolean;
  created_by_id: string;
  team_ids: string[];
}

export async function getAdminNotifications(
  queryString: string,
): Promise<PaginatedResponse<AdminNotification>> {
  return requestPaginated<AdminNotification>(`/admin/notification?${queryString}`);
}

export async function createAdminNotification(
  data: AdminNotificationCreate,
): Promise<AdminNotification> {
  return request<AdminNotification>("/admin/notification", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ---------------------------------------------------------------------------
// User – Notifications
// ---------------------------------------------------------------------------

export interface Notification {
  id: string;
  title: string;
  content: string;
  is_broadcast: boolean;
  created_at: string;
}

export interface NotificationListResponse {
  notifications: Notification[];
  last_read_at: string | null;
}

export async function getMyNotifications(): Promise<NotificationListResponse> {
  return request<NotificationListResponse>("/notification");
}

export async function markNotificationsRead(): Promise<void> {
  await rawRequest("/notification/read", { method: "POST" });
}

// ---------------------------------------------------------------------------
// Tags
// ---------------------------------------------------------------------------

export interface Tag {
  id: string;
  name: string;
  description: string;
  color: string;
}

// ---------------------------------------------------------------------------
// Public – Challenges (player-facing)
// ---------------------------------------------------------------------------

export interface PublicFile {
  id: string;
  name: string;
  original_filename: string;
  mime_type: string | null;
  file_size: number | null;
  url: string;
}

export interface PublicHint {
  id: string;
  title: string;
  cost: number;
  is_unlocked: boolean;
  content: string | null;
}

export type InputType = "input" | "code" | "text" | "mcq";

export interface PublicQuestion {
  id: string;
  label: string;
  description: string | null;
  is_locked: boolean;
  points: number;
  malus: number | null;
  input_type: InputType;
  is_solved: boolean;
  files: PublicFile[];
  hints: PublicHint[];
  tags: Tag[];
  options: string[] | null;
  multi_select: boolean;
}

export interface PublicChallenge {
  id: string;
  title: string;
  category_id: string | null;
  category_name: string | null;
  question_count: number;
  solved_count: number;
  tags: Tag[];
}

export interface PublicChallengeDetail extends PublicChallenge {
  challenge_type: string;
  description: string | null;
  sequential: boolean;
  questions: PublicQuestion[];
}

export interface SubmitResult {
  is_correct: boolean;
  already_solved: boolean;
  points_earned: number;
  message: string;
}

export async function getChallenges(): Promise<PublicChallenge[]> {
  return request<PublicChallenge[]>("/challenges");
}

export async function getChallenge(id: string): Promise<PublicChallengeDetail> {
  return request<PublicChallengeDetail>(`/challenges/${id}`);
}

export async function submitAnswer(
  challengeId: string,
  questionId: string,
  answer: string,
): Promise<SubmitResult> {
  return request<SubmitResult>(`/challenges/${challengeId}/${questionId}/submit`, {
    method: "POST",
    body: JSON.stringify({ answer }),
  });
}

export async function unlockHint(
  challengeId: string,
  questionId: string,
  hintId: string,
): Promise<PublicHint> {
  return request<PublicHint>(`/challenges/${challengeId}/${questionId}/hints/${hintId}/unlock`, {
    method: "POST",
  });
}

// ---------------------------------------------------------------------------
// Challenge – types & schemas (admin)
// ---------------------------------------------------------------------------

export interface JsonSchemaProperty {
  title?: string;
  type?: string;
  anyOf?: Array<{
    type?: string;
    format?: string;
    "x-ui-widget"?: string;
    items?: JsonSchemaProperty | { $ref: string };
  }>;
  format?: string;
  default?: unknown;
  description?: string;
  enum?: unknown[];
  // array support
  items?: JsonSchemaProperty | { $ref: string };
  // object support
  properties?: Record<string, JsonSchemaProperty>;
  required?: string[];
  // ref support
  $ref?: string;
  // UI widget hint (set via CodeStr and similar types in backend schemas)
  "x-ui-widget"?: string;
  // Inline select options (set via InlineSelect annotation in backend schemas)
  "x-ui-options"?: SelectOption[];
}

export interface SelectOption {
  value: string;
  label: string;
}

export interface JsonSchema {
  title?: string;
  type?: string;
  properties?: Record<string, JsonSchemaProperty>;
  required?: string[];
  $defs?: Record<string, JsonSchema>;
}

export interface ChallengeTypeInfo {
  type_name: string;
  create_schema: JsonSchema;
  update_schema: JsonSchema;
  read_schema: JsonSchema;
}

export interface SolutionTypeInfo {
  type_name: string;
  description: string | null;
  create_schema: JsonSchema;
  update_schema: JsonSchema;
  read_schema: JsonSchema;
  compatible_input_types: InputType[] | null;
}

// ---------------------------------------------------------------------------
// Admin – Challenges
// ---------------------------------------------------------------------------

export interface Challenge {
  id: string;
  challenge_type: string;
  title: string;
  is_active: boolean;
  sequential: boolean;
  category_id: string | null;
  category_name: string | null;
  question_count: number;
  tags: Tag[];
}

export interface ChallengeDetail extends Challenge {
  description: string | null;
  author_id: string | null;
}

export async function getChallengeTypes(): Promise<ChallengeTypeInfo[]> {
  return request<ChallengeTypeInfo[]>("/admin/challenge/types");
}

export async function getAdminChallenges(
  queryString: string,
): Promise<PaginatedResponse<Challenge>> {
  return requestPaginated<Challenge>(`/admin/challenge?${queryString}`);
}

export async function getAdminChallenge(id: string): Promise<ChallengeDetail> {
  return request<ChallengeDetail>(`/admin/challenge/${id}`);
}

export async function createChallenge(
  type: string,
  data: Record<string, unknown>,
): Promise<ChallengeDetail> {
  return request<ChallengeDetail>(`/admin/challenge/${type}`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateChallenge(
  id: string,
  data: Record<string, unknown>,
): Promise<ChallengeDetail> {
  return request<ChallengeDetail>(`/admin/challenge/${id}`, {
    method: "PUT",
    body: JSON.stringify({ id, ...data }),
  });
}

export async function deleteChallenge(id: string): Promise<void> {
  await rawRequest(`/admin/challenge/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Admin – Questions
// ---------------------------------------------------------------------------

export interface Question {
  id: string;
  challenge_id: string;
  label: string;
  description: string | null;
  index: number;
  points: number;
  malus: number | null;
  input_type: InputType;
  challenge_title: string | null;
  hint_count: number;
  solution_count: number;
  file_count: number;
  files: StoredFile[];
  tags: Tag[];
  [key: string]: unknown;
}

export async function getAdminQuestions(queryString: string): Promise<PaginatedResponse<Question>> {
  return requestPaginated<Question>(`/admin/question?${queryString}`);
}

export async function createQuestion(data: Record<string, unknown>): Promise<Question> {
  return request<Question>("/admin/question", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateQuestion(id: string, data: Record<string, unknown>): Promise<Question> {
  return request<Question>(`/admin/question/${id}`, {
    method: "PUT",
    body: JSON.stringify({ id, ...data }),
  });
}

export async function deleteQuestion(id: string): Promise<void> {
  await rawRequest(`/admin/question/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Admin – Solutions
// ---------------------------------------------------------------------------

export interface Solution {
  id: string;
  solve_type: string;
  question_id: string;
  [key: string]: unknown;
}

export async function getSolutionTypes(): Promise<SolutionTypeInfo[]> {
  return request<SolutionTypeInfo[]>("/admin/solution/types");
}

export async function getAdminSolutions(queryString: string): Promise<PaginatedResponse<Solution>> {
  return requestPaginated<Solution>(`/admin/solution?${queryString}`);
}

export async function getAdminSolution(id: string): Promise<Solution> {
  return request<Solution>(`/admin/solution/${id}`);
}

export async function createSolution(
  type: string,
  data: Record<string, unknown>,
): Promise<Solution> {
  return request<Solution>(`/admin/solution/${type}`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateSolution(id: string, data: Record<string, unknown>): Promise<Solution> {
  return request<Solution>(`/admin/solution/${id}`, {
    method: "PUT",
    body: JSON.stringify({ id, ...data }),
  });
}

export async function deleteSolution(id: string): Promise<void> {
  await rawRequest(`/admin/solution/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Admin – Hints
// ---------------------------------------------------------------------------

export interface Hint {
  id: string;
  question_id: string;
  title: string;
  cost: number;
  order: number;
  content?: string;
  question_label?: string | null;
}

export async function getAdminHints(queryString: string): Promise<PaginatedResponse<Hint>> {
  return requestPaginated<Hint>(`/admin/hint?${queryString}`);
}

export async function getAdminHint(id: string): Promise<Hint> {
  return request<Hint>(`/admin/hint/${id}`);
}

export async function createHint(data: {
  question_id: string;
  title: string;
  content: string;
  cost?: number;
  order?: number;
}): Promise<Hint> {
  return request<Hint>("/admin/hint", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateHint(
  id: string,
  data: Partial<Omit<Hint, "id" | "question_id">>,
): Promise<Hint> {
  return request<Hint>(`/admin/hint/${id}`, {
    method: "PUT",
    body: JSON.stringify({ id, ...data }),
  });
}

export async function deleteHint(id: string): Promise<void> {
  await rawRequest(`/admin/hint/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Admin – Categories
// ---------------------------------------------------------------------------

export interface Category {
  id: string;
  slug: string;
  name: string;
}

export async function getAdminCategories(queryString = ""): Promise<PaginatedResponse<Category>> {
  return requestPaginated<Category>(`/admin/category?${queryString}`);
}

export async function createCategory(data: { slug: string; name: string }): Promise<Category> {
  return request<Category>("/admin/category", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateCategory(
  id: string,
  data: { slug: string; name: string },
): Promise<Category> {
  return request<Category>(`/admin/category/${id}`, {
    method: "PUT",
    body: JSON.stringify({ id, ...data }),
  });
}

export async function deleteCategory(id: string): Promise<void> {
  await rawRequest(`/admin/category/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Admin – OAuth Providers
// ---------------------------------------------------------------------------

export interface AdminOAuthProvider {
  id: string;
  slug: string;
  name: string;
  client_id: string;
  discovery_url: string;
  scopes: string;
  icon_url: string | null;
  is_active: boolean;
}

export async function getAdminOAuthProviders(
  queryString = "",
): Promise<PaginatedResponse<AdminOAuthProvider>> {
  return requestPaginated<AdminOAuthProvider>(`/admin/oauth-provider?${queryString}`);
}

export async function createAdminOAuthProvider(data: {
  slug: string;
  name: string;
  client_id: string;
  client_secret: string;
  discovery_url: string;
  scopes: string;
  icon_url: string | null;
  is_active: boolean;
}): Promise<AdminOAuthProvider> {
  return request<AdminOAuthProvider>("/admin/oauth-provider", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAdminOAuthProvider(
  id: string,
  data: {
    slug?: string;
    name?: string;
    client_id?: string;
    client_secret?: string;
    discovery_url?: string;
    scopes?: string;
    icon_url?: string | null;
    is_active?: boolean;
  },
): Promise<AdminOAuthProvider> {
  return request<AdminOAuthProvider>(`/admin/oauth-provider/${id}`, {
    method: "PUT",
    body: JSON.stringify({ id, ...data }),
  });
}

export async function deleteAdminOAuthProvider(id: string): Promise<void> {
  await rawRequest(`/admin/oauth-provider/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Admin – Tags
// ---------------------------------------------------------------------------

export async function getAdminTags(queryString = ""): Promise<PaginatedResponse<Tag>> {
  return requestPaginated<Tag>(`/admin/tag?${queryString}`);
}

export async function createAdminTag(data: {
  name: string;
  description: string;
  color: string;
}): Promise<Tag> {
  return request<Tag>("/admin/tag", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAdminTag(
  id: string,
  data: { name: string; description: string; color: string },
): Promise<Tag> {
  return request<Tag>(`/admin/tag/${id}`, {
    method: "PUT",
    body: JSON.stringify({ id, ...data }),
  });
}

export async function deleteAdminTag(id: string): Promise<void> {
  await rawRequest(`/admin/tag/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Admin – Files
// ---------------------------------------------------------------------------

export interface StoredFile {
  id: string;
  name: string;
  s3_key: string;
  original_filename: string;
  mime_type: string | null;
  file_size: number | null;
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

export interface StoredFileDetail extends StoredFile {
  view_url: string;
  download_url: string;
}

export async function getAdminFiles(queryString: string): Promise<PaginatedResponse<StoredFile>> {
  return requestPaginated<StoredFile>(`/admin/file?${queryString}`);
}

export async function getAdminFile(id: string): Promise<StoredFileDetail> {
  return request<StoredFileDetail>(`/admin/file/${id}`);
}

async function multipartRequest(path: string, method: string, form: FormData): Promise<StoredFile> {
  // Do NOT set Content-Type — the browser sets it automatically with the boundary
  const res = await fetch(`${BASE}${path}`, {
    method,
    credentials: "include",
    body: form,
  });
  await throwIfNotOk(res);
  const json: ApiResponse<StoredFile> = await res.json();
  // biome-ignore lint/style/noNonNullAssertion: throwIfNotOk ensures response is OK before reaching here
  return json.data!;
}

export async function uploadAdminFile(
  name: string,
  file: File,
  isPublic = false,
): Promise<StoredFile> {
  const form = new FormData();
  form.append("name", name);
  form.append("upload", file);
  form.append("is_public", String(isPublic));
  return multipartRequest("/admin/file", "POST", form);
}

export async function updateAdminFile(
  id: string,
  opts: { name?: string; file?: File },
): Promise<StoredFile> {
  const form = new FormData();
  if (opts.name !== undefined) form.append("name", opts.name);
  if (opts.file !== undefined) form.append("upload", opts.file);
  return multipartRequest(`/admin/file/${id}`, "PUT", form);
}

export async function deleteAdminFile(id: string): Promise<void> {
  await rawRequest(`/admin/file/${id}`, { method: "DELETE" });
}

export async function markFilePublic(id: string, isPublic: boolean): Promise<StoredFile> {
  const form = new FormData();
  form.append("is_public", isPublic ? "1" : "0");
  return multipartRequest(`/admin/file/${id}`, "PUT", form);
}

// ---------------------------------------------------------------------------
// Custom Pages
// ---------------------------------------------------------------------------

export interface CustomPage {
  id: string;
  slug: string;
  title: string;
  content: string;
  is_published: boolean;
  nav_placement: "footer" | "nav" | null;
  created_at: string;
  updated_at: string;
}

export interface PublicPageSummary {
  slug: string;
  title: string;
  nav_placement: "footer" | "nav" | null;
}

export interface PublicPageDetail {
  slug: string;
  title: string;
  content: string;
  nav_placement: "footer" | "nav" | null;
}

export async function getAdminPages(queryString: string): Promise<PaginatedResponse<CustomPage>> {
  return requestPaginated<CustomPage>(`/admin/page?${queryString}`);
}

export async function getAdminPage(id: string): Promise<CustomPage> {
  return request<CustomPage>(`/admin/page/${id}`);
}

export async function createAdminPage(data: {
  slug: string;
  title: string;
  content?: string;
  is_published?: boolean;
  nav_placement?: "footer" | "nav" | null;
}): Promise<CustomPage> {
  return request<CustomPage>("/admin/page", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAdminPage(
  id: string,
  data: {
    slug?: string;
    title?: string;
    content?: string;
    is_published?: boolean;
    nav_placement?: "footer" | "nav" | null;
  },
): Promise<CustomPage> {
  return request<CustomPage>(`/admin/page/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteAdminPage(id: string): Promise<void> {
  await rawRequest(`/admin/page/${id}`, { method: "DELETE" });
}

export async function getPublishedPages(): Promise<PublicPageSummary[]> {
  return request<PublicPageSummary[]>("/page");
}

export async function getPublishedPage(slug: string): Promise<PublicPageDetail> {
  return request<PublicPageDetail>(`/page/${slug}`);
}

// ---------------------------------------------------------------------------
// Generic plugin sub-entity CRUD
// Used by the SubEntitySection component driven by SubEntityDef metadata.
// ---------------------------------------------------------------------------

export async function listSubEntities(
  endpoint: string,
  questionIdField: string,
  questionId: string,
): Promise<Record<string, unknown>[]> {
  const params = new URLSearchParams({
    [questionIdField]: questionId,
    items_per_page: "100",
  });
  const resp = await requestPaginated<Record<string, unknown>>(`${endpoint}?${params}`);
  return resp.data;
}

export async function createSubEntity(
  endpoint: string,
  data: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(endpoint, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateSubEntity(
  endpoint: string,
  id: string,
  data: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(`${endpoint}/${id}`, {
    method: "PUT",
    body: JSON.stringify({ id, ...data }),
  });
}

export async function deleteSubEntity(endpoint: string, id: string): Promise<void> {
  await rawRequest(`${endpoint}/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Public – Scoreboard
// ---------------------------------------------------------------------------

export interface ScoreboardEntry {
  rank: number;
  team_id: string;
  team_name: string;
  total: number;
}

export interface Scoreboard {
  entries: ScoreboardEntry[];
  computed_at: string;
}

export interface SolveDetail {
  submission_id: string;
  question_id: string;
  question_label: string;
  challenge_id: string;
  challenge_title: string;
  points_earned: number;
  wrong_attempts: number;
  solved_at: string;
}

export interface AdjustmentDetail {
  id: string;
  amount: number;
  reason: string;
  challenge_id: string | null;
  challenge_title: string | null;
  applied_at: string;
}

export interface TeamScoreDetail {
  team_id: string;
  team_name: string;
  total: number;
  solve_points: number;
  adjustment_points: number;
  solves: SolveDetail[];
  adjustments: AdjustmentDetail[];
  computed_at: string;
}

export interface ScoreEvent {
  ts: string;
  cumulative: number;
}

export interface TeamScoreSeries {
  team_id: string;
  team_name: string;
  rank: number;
  events: ScoreEvent[];
}

export interface ScoreboardHistory {
  series: TeamScoreSeries[];
  computed_at: string;
}

export async function getScoreboard(): Promise<Scoreboard> {
  return request<Scoreboard>("/scoreboard");
}

export interface AdminScoreboardEntry {
  rank: number;
  team_id: string;
  team_name: string;
  total: number;
  solve_points: number;
  adjustment_points: number;
  solve_count: number;
  last_solve_at: string | null;
}

export interface AdminScoreboard {
  entries: AdminScoreboardEntry[];
  computed_at: string;
}

export async function getAdminScoreboard(): Promise<AdminScoreboard> {
  return request<AdminScoreboard>("/admin/scoreboard");
}

export async function getTeamScore(teamId: string): Promise<TeamScoreDetail> {
  return request<TeamScoreDetail>(`/scoreboard/team/${teamId}`);
}

export async function getScoreboardHistory(limit = 10): Promise<ScoreboardHistory> {
  return request<ScoreboardHistory>(`/scoreboard/history?limit=${limit}`);
}

// ---------------------------------------------------------------------------
// Admin – Score Adjustments
// ---------------------------------------------------------------------------

export interface ScoreAdjustment {
  id: string;
  team_id: string;
  amount: number;
  reason: string;
  challenge_id: string | null;
  created_by_id: string;
  team_name: string | null;
  challenge_title: string | null;
  created_by_username: string | null;
}

export async function getAdminScoreAdjustments(
  queryString: string,
): Promise<PaginatedResponse<ScoreAdjustment>> {
  return requestPaginated<ScoreAdjustment>(`/admin/score-adjustment?${queryString}`);
}

export async function createAdminScoreAdjustment(data: {
  team_id: string;
  amount: number;
  reason: string;
  challenge_id?: string | null;
}): Promise<ScoreAdjustment> {
  return request<ScoreAdjustment>("/admin/score-adjustment", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAdminScoreAdjustment(
  id: string,
  data: { amount?: number; reason?: string },
): Promise<ScoreAdjustment> {
  return request<ScoreAdjustment>(`/admin/score-adjustment/${id}`, {
    method: "PUT",
    body: JSON.stringify({ id, ...data }),
  });
}

export async function deleteAdminScoreAdjustment(id: string): Promise<void> {
  await rawRequest(`/admin/score-adjustment/${id}`, { method: "DELETE" });
}

export async function invalidateScoreboardCache(teamId?: string): Promise<void> {
  const params = teamId ? `?team_id=${teamId}` : "";
  await rawRequest(`/admin/scoreboard/invalidate${params}`, { method: "POST" });
}

// ---------------------------------------------------------------------------
// OAuth helpers
// ---------------------------------------------------------------------------

export function oauthAuthorizeUrl(slug: string, redirectUrl?: string): string {
  const params = redirectUrl ? `?redirect_url=${encodeURIComponent(redirectUrl)}` : "";
  return `${BASE}/auth/providers/${slug}/authorize${params}`;
}

// ---------------------------------------------------------------------------
// Admin – OAuth Clients (OAuth Server)
// ---------------------------------------------------------------------------

export interface AdminOAuthClient {
  id: string;
  name: string;
  description: string | null;
  client_id: string;
  redirect_uris: string;
  allowed_scopes: string;
  is_active: boolean;
  created_at: string;
  endpoints: {
    discovery: string;
    authorize: string;
    token: string;
    userinfo: string;
  };
}

export interface AdminOAuthClientCreated extends AdminOAuthClient {
  /** Raw client secret — shown only at creation time. */
  client_secret: string;
}

export async function getAdminOAuthClients(
  queryString = "",
): Promise<PaginatedResponse<AdminOAuthClient>> {
  return requestPaginated<AdminOAuthClient>(`/admin/oauth-client?${queryString}`);
}

export async function createAdminOAuthClient(data: {
  name: string;
  description: string | null;
  redirect_uris: string;
  allowed_scopes: string;
  is_active: boolean;
}): Promise<AdminOAuthClientCreated> {
  return request<AdminOAuthClientCreated>("/admin/oauth-client", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAdminOAuthClient(
  id: string,
  data: {
    name?: string;
    description?: string | null;
    redirect_uris?: string;
    allowed_scopes?: string;
    is_active?: boolean;
  },
): Promise<AdminOAuthClient> {
  return request<AdminOAuthClient>(`/admin/oauth-client/${id}`, {
    method: "PUT",
    body: JSON.stringify({ id, ...data }),
  });
}

export async function deleteAdminOAuthClient(id: string): Promise<void> {
  await rawRequest(`/admin/oauth-client/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Admin – Events
// ---------------------------------------------------------------------------

export interface AdminEvent {
  id: string;
  created_at: string;
  event_type: string;
  ip: string | null;
  meta: Record<string, unknown>;
  actor_id: string | null;
  actor_username: string | null;
  team_id: string | null;
  team_name: string | null;
  challenge_id: string | null;
  challenge_title: string | null;
}

export async function getAdminEvents(queryString: string): Promise<PaginatedResponse<AdminEvent>> {
  return requestPaginated<AdminEvent>(`/admin/event?${queryString}`);
}

export async function getAdminUserEvents(
  userId: string,
  queryString: string,
): Promise<PaginatedResponse<AdminEvent>> {
  return requestPaginated<AdminEvent>(`/admin/user/${userId}/events?${queryString}`);
}

// ---------------------------------------------------------------------------
// Admin – Stats
// ---------------------------------------------------------------------------

export interface QuestionStats {
  question_id: string;
  question_label: string;
  question_index: number;
  attempt_count: number;
  correct_count: number;
  teams_attempted: number;
  teams_solved: number;
  hint_unlock_count: number;
  hint_cost_spent: number;
  first_blood_team_name: string | null;
  first_blood_at: string | null;
}

export interface ChallengeStats {
  challenge_id: string;
  challenge_title: string;
  question_count: number;
  attempt_count: number;
  correct_count: number;
  teams_attempted: number;
  teams_solved: number;
  hint_unlock_count: number;
  hint_cost_spent: number;
  first_blood_team_id: string | null;
  first_blood_team_name: string | null;
  first_blood_at: string | null;
  questions: QuestionStats[];
}

export interface AdminTeamChallengeStats extends TeamChallengeStats {
  hint_unlock_count: number;
  hint_cost_spent: number;
}

export async function getAdminAllChallengeStats(): Promise<ChallengeStats[]> {
  return request<ChallengeStats[]>("/admin/stats/challenges");
}

export async function getAdminTeamChallengeStats(
  teamId: string,
): Promise<AdminTeamChallengeStats[]> {
  return request<AdminTeamChallengeStats[]>(`/admin/team/${teamId}/challenge-stats`);
}

// ---------------------------------------------------------------------------
// OAuth2 Server — consent flow (user-facing)
// ---------------------------------------------------------------------------

export interface OAuthConsentInfo {
  client_id: string;
  client_name: string;
  client_description: string | null;
  requested_scopes: string[];
  username: string;
}

export async function getOAuthConsentInfo(
  clientId: string,
  scope: string,
): Promise<OAuthConsentInfo> {
  return request<OAuthConsentInfo>(
    `/oauth2/client-info?client_id=${encodeURIComponent(clientId)}&scope=${encodeURIComponent(scope)}`,
  );
}

export async function approveOAuthConsent(params: {
  client_id: string;
  redirect_uri: string;
  scope: string;
  state?: string;
}): Promise<{ redirect_to: string }> {
  return request<{ redirect_to: string }>("/oauth2/authorize/approve", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

// ---------------------------------------------------------------------------
// Admin – Plugins
// ---------------------------------------------------------------------------

export interface Plugin {
  key: string;
  name: string;
  display_name: string;
  version: string | null;
  description: string | null;
  authors: string[];
  repo_url: string | null;
  homepage_url: string | null;
  is_builtin: boolean;
  is_active: boolean;
  is_official: boolean;
  load_error: string | null;
}

export async function getAdminPlugins(): Promise<Plugin[]> {
  return request<Plugin[]>("/admin/plugins");
}

// ---------------------------------------------------------------------------
// Admin – Scheduler
// ---------------------------------------------------------------------------

export interface SchedulerJobType {
  type_name: string;
  create_schema: JsonSchema;
  update_schema: JsonSchema;
}

export interface SchedulerJob {
  id: string;
  name: string;
  job_type: string;
  is_active: boolean;
  scheduled_at: string;
  params: Record<string, unknown>;
  last_run: string | null;
  created_at: string;
  created_by_id: string;
}

export interface SchedulerTask {
  id: string;
  job_id: string;
  status: "pending" | "success" | "failed";
  started_at: string;
  completed_at: string | null;
  error: string | null;
  created_at: string;
}

export interface SchedulerJobDetail extends SchedulerJob {
  tasks: SchedulerTask[];
}

export async function getAdminSchedulerJobTypes(): Promise<SchedulerJobType[]> {
  return request<SchedulerJobType[]>("/admin/scheduler/jobs/types");
}

export async function getAdminSchedulerJobs(
  queryString: string,
): Promise<PaginatedResponse<SchedulerJob>> {
  return requestPaginated<SchedulerJob>(`/admin/scheduler/jobs?${queryString}`);
}

export async function getAdminSchedulerJob(id: string): Promise<SchedulerJobDetail> {
  return request<SchedulerJobDetail>(`/admin/scheduler/jobs/${id}`);
}

export async function createAdminSchedulerJob(data: {
  name: string;
  job_type: string;
  scheduled_at: string;
  is_active: boolean;
  params: Record<string, unknown>;
}): Promise<SchedulerJob> {
  return request<SchedulerJob>("/admin/scheduler/jobs", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAdminSchedulerJob(
  id: string,
  data: {
    name?: string;
    scheduled_at?: string;
    is_active?: boolean;
    params?: Record<string, unknown>;
  },
): Promise<SchedulerJob> {
  return request<SchedulerJob>(`/admin/scheduler/jobs/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteAdminSchedulerJob(id: string): Promise<void> {
  await rawRequest(`/admin/scheduler/jobs/${id}`, { method: "DELETE" });
}

export async function runAdminSchedulerJob(id: string): Promise<SchedulerTask> {
  return request<SchedulerTask>(`/admin/scheduler/jobs/${id}/run`, {
    method: "POST",
  });
}
