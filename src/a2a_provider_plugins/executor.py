"""Official A2A SDK executor backed by a provider adapter."""

from __future__ import annotations

from a2a.helpers.proto_helpers import new_task_from_user_message
from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import Part, TaskState

from .adapter import ProviderAdapter


class ProviderAgentExecutor(AgentExecutor):
    """Map the A2A task lifecycle to a thin provider implementation."""

    def __init__(self, adapter: ProviderAdapter) -> None:
        self._adapter = adapter

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task
        if task is None:
            if context.message is None:
                raise ValueError("A2A request has no message")
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.update_status(TaskState.TASK_STATE_WORKING)
        reply = await self._adapter.send(
            context.get_user_input(),
            context_id=task.context_id,
            task_id=task.id,
        )
        if not reply.text.strip():
            raise ValueError("Provider returned an empty response")
        await updater.add_artifact(
            [Part(text=reply.text)],
            name="provider-response",
            last_chunk=True,
        )
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        if not context.task_id or not context.context_id:
            raise ValueError("Cancellation requires a task and context")
        await self._adapter.cancel(task_id=context.task_id)
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.cancel()

