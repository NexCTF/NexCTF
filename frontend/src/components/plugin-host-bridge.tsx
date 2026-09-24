import { useRouter } from "@tanstack/react-router";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/lib/auth";
import { pluginHost } from "@/lib/plugins";

/** Keeps `window.__nexctf__.host` in step with the signed-in user, locale and router. */
export function PluginHostBridge() {
  const { user } = useAuth();
  const router = useRouter();
  const { i18n } = useTranslation();

  useEffect(() => {
    pluginHost.user = user ? { id: user.id, username: user.username, role: user.role } : null;
  }, [user]);

  const language = i18n.resolvedLanguage ?? i18n.language;
  useEffect(() => {
    pluginHost.language = language;
  }, [language]);

  useEffect(() => {
    pluginHost.navigate = (path) => router.history.push(path);
  }, [router]);

  return null;
}
