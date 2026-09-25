"""Background tasks: plugins declare ``TaskDef``/``CronDef`` and queue work here."""

from nexctf.tasks.queue import enqueue

__all__ = ["enqueue"]
