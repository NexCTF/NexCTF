import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useCallback, useContext } from "react";
import { login as apiLogin, logout as apiLogout, getMe, type User } from "@/lib/api";
import { closeSSE } from "@/lib/sse";

export interface AuthContext {
  user: User | null;
  isLoading: boolean;
  login: (
    username: string,
    password: string,
    totpCode?: string,
    captchaToken?: string,
  ) => Promise<void>;
  logout: () => Promise<void>;
}

/** Exported so tests can provide a value without mounting the real provider. */
export const AuthCtx = createContext<AuthContext | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();

  const { data: user = null, isLoading } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: getMe,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const login = useCallback(
    async (username: string, password: string, totpCode?: string, captchaToken?: string) => {
      await apiLogin(username, password, totpCode, captchaToken);
      const user = await getMe();
      qc.setQueryData(["auth", "me"], user);
    },
    [qc],
  );

  const logout = useCallback(async () => {
    await apiLogout();
    closeSSE();
    qc.setQueryData(["auth", "me"], null);
  }, [qc]);

  return <AuthCtx.Provider value={{ user, isLoading, login, logout }}>{children}</AuthCtx.Provider>;
}

export function useAuth(): AuthContext {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
