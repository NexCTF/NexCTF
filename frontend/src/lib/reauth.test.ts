import { afterEach, expect, it, vi } from "vitest";
import { ApiError, createMyToken } from "@/lib/api";
import { promptReauth, REAUTH_REQUIRED, setReauthPrompt } from "@/lib/reauth";

function reply(status: number, body: unknown) {
  return { ok: status < 400, status, statusText: "", json: async () => body };
}

const STALE = reply(401, {
  message: "Re-authentication required",
  error_code: REAUTH_REQUIRED,
  data: { max_age: 600 },
});
const CREATED = reply(201, { data: { id: "t1", token: "nexctf_x" } });

function stubFetch(...responses: ReturnType<typeof reply>[]) {
  const fetchMock = vi.fn();
  for (const response of responses) fetchMock.mockResolvedValueOnce(response);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  setReauthPrompt(null);
  vi.unstubAllGlobals();
});

it("retries the request once the user signs in again", async () => {
  const fetchMock = stubFetch(STALE, CREATED);
  const prompt = vi.fn().mockResolvedValue(true);
  setReauthPrompt(prompt);

  const token = await createMyToken("ci", ["read:challenges"]);

  expect(token).toEqual({ id: "t1", token: "nexctf_x" });
  expect(prompt).toHaveBeenCalledOnce();
  expect(fetchMock).toHaveBeenCalledTimes(2);
  expect(fetchMock.mock.calls[1][1].body).toBe(fetchMock.mock.calls[0][1].body);
});

it("surfaces the original error when the prompt is dismissed", async () => {
  const fetchMock = stubFetch(STALE);
  setReauthPrompt(vi.fn().mockResolvedValue(false));

  const err = await createMyToken("ci", []).catch((e: unknown) => e);

  expect(err).toBeInstanceOf(ApiError);
  expect((err as ApiError).errCode).toBe(REAUTH_REQUIRED);
  expect(fetchMock).toHaveBeenCalledOnce();
});

it("does not prompt for an ordinary 401", async () => {
  stubFetch(reply(401, { message: "Unauthorized", error_code: "AUTH-401" }));
  const prompt = vi.fn();
  setReauthPrompt(prompt);

  await createMyToken("ci", []).catch(() => undefined);

  expect(prompt).not.toHaveBeenCalled();
});

it("shares one prompt between concurrent requests", async () => {
  let accept: (ok: boolean) => void = () => {};
  const prompt = vi.fn(() => new Promise<boolean>((resolve) => (accept = resolve)));
  setReauthPrompt(prompt);

  const first = promptReauth();
  const second = promptReauth();
  accept(true);

  expect(await Promise.all([first, second])).toEqual([true, true]);
  expect(prompt).toHaveBeenCalledOnce();
});

it("declines when no prompt is mounted", async () => {
  expect(await promptReauth()).toBe(false);
});
