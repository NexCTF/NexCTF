import { expect, it, vi } from "vitest";
import { ApiError, getMe } from "@/lib/api";
import { createQueryClient } from "@/lib/query-client";
import { user } from "@/test/fixtures";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getMe: vi.fn(),
}));

function clientWithIdentity() {
  const client = createQueryClient();
  client.setQueryData(["auth", "me"], { id: "u1", username: "player" });
  return client;
}

async function runQuery(client: ReturnType<typeof createQueryClient>, error: unknown) {
  await client
    .fetchQuery({
      queryKey: ["challenges"],
      queryFn: () => Promise.reject(error),
      retry: false,
    })
    .catch(() => undefined);
}

it("forgets the cached identity when a query 401s", async () => {
  const client = clientWithIdentity();

  await runQuery(client, new ApiError(401, "Unauthorized"));

  expect(client.getQueryData(["auth", "me"])).toBeNull();
});

async function runMutation(client: ReturnType<typeof createQueryClient>, error: unknown) {
  await client
    .getMutationCache()
    .build(client, { mutationFn: () => Promise.reject(error) })
    .execute(undefined)
    .catch(() => undefined);
}

it("forgets the cached identity when a mutation 401s on a dead session", async () => {
  const client = clientWithIdentity();
  vi.mocked(getMe).mockRejectedValue(new ApiError(401, "Unauthorized"));

  await runMutation(client, new ApiError(401, "Unauthorized"));

  await vi.waitFor(() => expect(client.getQueryData(["auth", "me"])).toBeNull());
});

it("keeps the identity when a mutation 401s on a wrong password or code", async () => {
  const client = clientWithIdentity();
  const me = user({ username: "player" });
  vi.mocked(getMe).mockResolvedValue(me);

  await runMutation(client, new ApiError(401, "Invalid OTP code"));

  await vi.waitFor(() => expect(client.getQueryData(["auth", "me"])).toEqual(me));
});

it("keeps the identity on other failures", async () => {
  const client = clientWithIdentity();

  await runQuery(client, new ApiError(403, "Forbidden"));
  await runQuery(client, new ApiError(500, "Boom"));
  await runQuery(client, new Error("network down"));

  expect(client.getQueryData(["auth", "me"])).not.toBeNull();
});
