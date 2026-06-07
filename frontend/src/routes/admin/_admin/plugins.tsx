import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { AlertTriangle, Box, ExternalLink, Puzzle, ShieldCheck, User } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { getAdminPlugins, type Plugin } from "@/lib/api";

export const Route = createFileRoute("/admin/_admin/plugins")({
  component: PluginsPage,
});

function VersionBadge({ version }: { version: string | null }) {
  if (!version) return null;
  return (
    <span className="rounded bg-muted px-1.5 py-0.5 text-[11px] font-mono text-muted-foreground">
      v{version}
    </span>
  );
}

function StatusBadge({ plugin }: { plugin: Plugin }) {
  if (plugin.is_builtin) {
    return (
      <span className="inline-flex items-center rounded-full bg-blue-500/10 px-2 py-0.5 text-xs font-medium text-blue-600 dark:text-blue-400">
        Built-in
      </span>
    );
  }
  return plugin.is_active ? (
    <span className="inline-flex items-center rounded-full bg-green-500/10 px-2 py-0.5 text-xs font-medium text-green-600 dark:text-green-400">
      Active
    </span>
  ) : (
    <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
      Inactive
    </span>
  );
}

function OfficialBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-600 dark:text-amber-400">
      <ShieldCheck className="size-3" />
      Official
    </span>
  );
}

function PluginCard({ plugin }: { plugin: Plugin }) {
  return (
    <Card className="flex flex-col">
      <CardContent className="flex flex-col gap-3 pt-5">
        {/* Header row */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <Box className="size-4 shrink-0 text-muted-foreground" />
            <span className="font-semibold truncate">{plugin.display_name}</span>
            <VersionBadge version={plugin.version} />
            {plugin.is_official && <OfficialBadge />}
          </div>
          <StatusBadge plugin={plugin} />
        </div>

        {/* Description */}
        {plugin.description && (
          <p className="text-sm text-muted-foreground leading-relaxed">{plugin.description}</p>
        )}

        {/* Meta rows */}
        <div className="flex flex-col gap-1.5 text-xs text-muted-foreground">
          {plugin.authors.length > 0 && (
            <div className="flex items-center gap-1.5">
              <User className="size-3 shrink-0" />
              <span>{plugin.authors.join(", ")}</span>
            </div>
          )}

          {plugin.repo_url && (
            <div className="flex items-center gap-1.5">
              <ExternalLink className="size-3 shrink-0" />
              <a
                href={plugin.repo_url}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-foreground hover:underline truncate"
              >
                {plugin.repo_url}
              </a>
            </div>
          )}
        </div>

        {/* Load error */}
        {plugin.load_error && (
          <div className="flex items-start gap-1.5 rounded bg-destructive/10 px-2 py-1.5 text-xs text-destructive">
            <AlertTriangle className="size-3 shrink-0 mt-0.5" />
            <span className="break-words font-mono">{plugin.load_error}</span>
          </div>
        )}

        {/* Key */}
        <div className="mt-auto pt-1 border-t">
          <span className="text-[11px] font-mono text-muted-foreground/60">{plugin.key}</span>
        </div>
      </CardContent>
    </Card>
  );
}

function PluginSection({ title, plugins }: { title: string; plugins: Plugin[] }) {
  if (plugins.length === 0) return null;
  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </h2>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {plugins.map((p) => (
          <PluginCard key={p.key} plugin={p} />
        ))}
      </div>
    </section>
  );
}

function PluginsPage() {
  const { data: plugins = [], isLoading } = useQuery({
    queryKey: ["admin", "plugins"],
    queryFn: getAdminPlugins,
  });

  const builtin = plugins.filter((p) => p.is_builtin);
  const external = plugins.filter((p) => !p.is_builtin);

  return (
    <div className="p-8 space-y-8">
      <div className="flex items-center gap-3">
        <Puzzle className="size-6 text-muted-foreground" />
        <h1 className="text-2xl font-bold">Plugins</h1>
        {!isLoading && (
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
            {plugins.length}
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-24">
          <p className="text-muted-foreground text-sm">Loading…</p>
        </div>
      ) : (
        <div className="space-y-10">
          <PluginSection title="Built-in" plugins={builtin} />
          <PluginSection title="External" plugins={external} />
          {plugins.length === 0 && (
            <p className="text-muted-foreground text-sm">No plugins loaded.</p>
          )}
        </div>
      )}
    </div>
  );
}
