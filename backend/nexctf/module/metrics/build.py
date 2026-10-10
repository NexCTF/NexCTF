"""Running NexCTF version and loaded plugins."""

from __future__ import annotations

from prometheus_client.core import GaugeMetricFamily, Metric

from nexctf.module.info.version import CURRENT_VERSION
from nexctf.plugins.loader import PluginMeta, get_plugin_metadata


def _state(meta: PluginMeta) -> str:
    """How a plugin ended up after loading."""
    if meta.load_error:
        return "error"
    if meta.is_disabled:
        return "disabled"
    return "active"


def build_metrics() -> list[Metric]:
    """NexCTF version and one sample per known plugin."""
    build = GaugeMetricFamily(
        "nexctf_build_info", "Running NexCTF version.", labels=["version"]
    )
    build.add_metric([CURRENT_VERSION], 1)
    plugins = GaugeMetricFamily(
        "nexctf_plugin_info",
        "Plugins known to this worker.",
        labels=["plugin", "version", "builtin", "state"],
    )
    for meta in sorted(get_plugin_metadata().values(), key=lambda m: m.key):
        plugins.add_metric(
            [meta.key, meta.version or "", str(meta.is_builtin).lower(), _state(meta)],
            1,
        )
    return [build, plugins]
