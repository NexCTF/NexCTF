import { createFileRoute } from "@tanstack/react-router";
import { PluginPage } from "@/components/plugin-page";

export const Route = createFileRoute("/_user/plugins/$key/$")({
  component: UserPluginPage,
});

function UserPluginPage() {
  const { key, _splat } = Route.useParams();
  return <PluginPage scope="user" pluginKey={key} subpath={_splat ?? ""} />;
}
