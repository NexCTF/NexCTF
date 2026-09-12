import { expect, it } from "vitest";
import { ApiError } from "@/lib/api";
import { createQueryClient } from "@/lib/query-client";

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

it("forgets the cached identity when a mutation 401s", async () => {
  const client = clientWithIdentity();

  await client
    .getMutationCache()
    .build(client, { mutationFn: () => Promise.reject(new ApiError(401, "Unauthorized")) })
    .execute(undefined)
    .catch(() => undefined);

  expect(client.getQueryData(["auth", "me"])).toBeNull();
});

it("keeps the identity on other failures", async () => {
  const client = clientWithIdentity();

  await runQuery(client, new ApiError(403, "Forbidden"));
  await runQuery(client, new ApiError(500, "Boom"));
  await runQuery(client, new Error("network down"));

  expect(client.getQueryData(["auth", "me"])).not.toBeNull();
});
