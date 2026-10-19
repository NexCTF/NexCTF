import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";
import { ApiError, getMe, isReauthRequired } from "@/lib/api";

/** A 401 on a dead session; one asking for a fresh sign-in is not counted. */
function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401 && !isReauthRequired(error);
}

/**
 * A session killed server-side (revoked by an admin, expired, signed out
 * elsewhere) surfaces only as 401s on whatever the page queries next. The
 * cached identity would otherwise stay valid until its staleTime elapsed,
 * leaving the user on a page that can no longer load anything. Dropping it
 * here lets the route guards send them to login on the next render.
 */
function forgetIdentityOn401(client: QueryClient, error: unknown): void {
  if (isUnauthorized(error)) {
    client.setQueryData(["auth", "me"], null);
  }
}

function recheckIdentityOn401(client: QueryClient, error: unknown): void {
  if (isUnauthorized(error)) {
    void client
      .fetchQuery({ queryKey: ["auth", "me"], queryFn: getMe, staleTime: 0 })
      .catch(() => undefined);
  }
}

/** Retry network and server failures; a client error answers the same way again. */
function retryTransientFailures(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status < 500 && ![408, 429].includes(error.status)) {
    return false;
  }
  return failureCount < 3;
}

export function createQueryClient(): QueryClient {
  const client: QueryClient = new QueryClient({
    defaultOptions: { queries: { staleTime: 30_000, retry: retryTransientFailures } },
    queryCache: new QueryCache({
      onError: (error) => forgetIdentityOn401(client, error),
    }),
    mutationCache: new MutationCache({
      onError: (error) => recheckIdentityOn401(client, error),
    }),
  });
  return client;
}
