import { randomBytes } from "node:crypto";
import { type APIRequestContext, expect, request } from "@playwright/test";
import type { SeededQuestion } from "./challenges";

/** The backend, reached directly rather than through the Vite proxy. */
const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000";
/** Full-admin token seeded by the development `token` fixture. */
const ADMIN_TOKEN = process.env.E2E_ADMIN_TOKEN ?? "nexctf_admin_token";

export interface Account {
  id: string;
  username: string;
  email: string;
  password: string;
}

/** A name no other test (or earlier run against the same database) has used. */
export function uniqueName(prefix: string): string {
  const random = randomBytes(3).toString("hex");
  return `${prefix}_${Date.now().toString(36)}${random}`;
}

/** Request context that authenticates with `token` alone, as a script would. */
export function tokenApi(token: string): Promise<APIRequestContext> {
  return request.newContext({
    baseURL: `${API_URL}/api/v1/`,
    extraHTTPHeaders: { Authorization: `Bearer ${token}` },
  });
}

/** Request context authenticated as the seeded admin, for test setup only. */
export function adminApi(): Promise<APIRequestContext> {
  return tokenApi(ADMIN_TOKEN);
}

/** Create a verified player account, skipping registration and its rate limit. */
export async function createAccount(admin: APIRequestContext): Promise<Account> {
  const username = uniqueName("e2e");
  const account = { username, email: `${username}@e2e.nexctf.lan`, password: `pw-${username}` };
  const res = await admin.post("admin/user", { data: account });
  expect(res.status(), await res.text()).toBe(201);
  const { data } = await res.json();
  return { ...account, id: data.id };
}

/** Change an account the way an admin would from the panel. */
export async function updateAccount(
  admin: APIRequestContext,
  account: Account,
  changes: { email?: string; is_active?: boolean },
): Promise<void> {
  const res = await admin.put(`admin/user/${account.id}`, { data: { id: account.id, ...changes } });
  expect(res.ok(), await res.text()).toBe(true);
}

/** Sign `api` in as `account`; a page's `request` shares its cookies with the page. */
export async function signIn(api: APIRequestContext, account: Account): Promise<void> {
  const res = await api.post("/api/v1/auth/token", {
    form: { username: account.username, password: account.password },
  });
  expect(res.status(), await res.text()).toBe(204);
}

export interface TeamSummary {
  id: string;
  name: string;
  invite_code: string;
}

/** Create a team owned by whoever `api` is signed in as. */
export async function createTeam(api: APIRequestContext): Promise<TeamSummary> {
  const res = await api.post("/api/v1/me/team", { data: { name: uniqueName("team") } });
  expect(res.status(), await res.text()).toBe(201);
  return (await res.json()).data;
}

/** Join the team behind `code` as whoever `api` is signed in as. */
export async function joinTeam(api: APIRequestContext, code: string): Promise<void> {
  const res = await api.post("/api/v1/me/team/join", { data: { code } });
  expect(res.ok(), await res.text()).toBe(true);
}

/** The submit endpoint of `question`, relative to `/api/v1/`. */
export function submitPath(question: SeededQuestion): string {
  return `challenges/${question.challengeId}/${question.questionId}/submit`;
}

/** Solve `question` as whoever `api` is signed in as. */
export async function submitFlag(api: APIRequestContext, question: SeededQuestion): Promise<void> {
  const res = await api.post(`/api/v1/${submitPath(question)}`, {
    data: { answer: question.flag },
  });
  expect(res.ok(), await res.text()).toBe(true);
  expect((await res.json()).data.is_correct).toBe(true);
}
