import { createRootRoute, createRoute } from "@tanstack/react-router";
import { waitFor } from "@testing-library/react";
import { expect, it } from "vitest";
import { pluginHost } from "@/lib/plugins";
import { user } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { PluginHostBridge } from "./plugin-host-bridge";

const route = createRoute({
  getParentRoute: () => createRootRoute(),
  path: "/",
  component: PluginHostBridge,
});

it("exposes the signed-in user, the locale and host navigation to plugins", async () => {
  const { router } = renderRoute(route, { auth: { user: user({ username: "alice" }) } });

  await waitFor(() => expect(pluginHost.user?.username).toBe("alice"));
  expect(pluginHost.user).not.toHaveProperty("email");
  expect(pluginHost.language).toBe("en");
  expect(window.__nexctf__.host).toBe(pluginHost);

  pluginHost.navigate("/challenges");
  await waitFor(() => expect(router.state.location.pathname).toBe("/challenges"));
});
