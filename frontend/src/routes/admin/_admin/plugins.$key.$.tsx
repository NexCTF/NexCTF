import { createFileRoute } from "@tanstack/react-router";
import { PluginPage } from "@/components/plugin-page";

export const Route = createFileRoute("/admin/_admin/plugins/$key/$")({
  component: AdminPluginPage,
});

function AdminPluginPage() {
  const { key, _splat } = Route.useParams();
  return <PluginPage scope="admin" pluginKey={key} subpath={_splat ?? ""} />;
}
