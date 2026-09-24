import { Component, type ComponentType, type ReactNode, Suspense, use } from "react";
import { bootstrapPlugins, getPluginsForSlot, pluginsReady } from "@/lib/plugins";

interface PluginSlotProps {
  name: string;
  challengeType?: string;
  context: Record<string, unknown>;
}

export class PluginErrorBoundary extends Component<
  { pluginKey: string; fallback?: ReactNode; children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(err: unknown) {
    console.error(`[plugin:${this.props.pluginKey}]`, err);
  }
  render() {
    return this.state.failed ? (this.props.fallback ?? null) : this.props.children;
  }
}

function PluginSlotInner({ name, challengeType, context }: PluginSlotProps) {
  void bootstrapPlugins();
  use(pluginsReady());
  const plugins = getPluginsForSlot(name, challengeType);
  if (plugins.length === 0) return null;

  return (
    <>
      {plugins.map((plugin) => {
        const Comp = plugin.slots[name] as ComponentType<Record<string, unknown>> | undefined;
        if (!Comp) return null;
        return (
          <PluginErrorBoundary key={plugin.key} pluginKey={plugin.key}>
            <Comp {...context} />
          </PluginErrorBoundary>
        );
      })}
    </>
  );
}

export function PluginSlot(props: PluginSlotProps) {
  return (
    <Suspense fallback={null}>
      <PluginSlotInner {...props} />
    </Suspense>
  );
}
