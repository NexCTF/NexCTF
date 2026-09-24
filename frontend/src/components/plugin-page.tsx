import { Suspense, use } from "react";
import { useTranslation } from "react-i18next";
import { PluginErrorBoundary } from "@/components/plugin-slot";
import { bootstrapPlugins, findPluginPage, type PluginScope } from "@/lib/plugins";

interface PluginPageProps {
  scope: PluginScope;
  pluginKey: string;
  subpath: string;
}

function PluginMessage({ text }: { text: string }) {
  return (
    <div className="flex items-center justify-center py-32">
      <p className="text-lg font-semibold">{text}</p>
    </div>
  );
}

function PluginPageInner({ scope, pluginKey, subpath }: PluginPageProps) {
  const { t } = useTranslation();
  use(bootstrapPlugins(scope));
  const found = findPluginPage(scope, pluginKey, subpath);
  if (!found) {
    return <PluginMessage text={t("errors.not_found", { defaultValue: "Page not found" })} />;
  }
  const { Page, props } = found;
  return (
    <PluginErrorBoundary
      key={`${pluginKey}/${props.path}`}
      pluginKey={pluginKey}
      fallback={
        <PluginMessage
          text={t("plugins.page_failed", {
            defaultValue: "This plugin page failed to render. Details are in the browser console.",
          })}
        />
      }
    >
      <Page {...props} />
    </PluginErrorBoundary>
  );
}

/** Render the page a plugin registered for `subpath`, once its bundles have loaded. */
export function PluginPage(props: PluginPageProps) {
  return (
    <Suspense fallback={null}>
      <PluginPageInner {...props} />
    </Suspense>
  );
}
