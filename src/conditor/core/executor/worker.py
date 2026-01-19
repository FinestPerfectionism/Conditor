import time
import json
import logging
import asyncio
import json
import logging
from pathlib import Path
from typing import Callable, Any, Awaitable

from ..planner.models import BuildPlan, BuildStep

logger = logging.getLogger(__name__)


class Executor:
    """Executes a BuildPlan step-by-step with retries, backoff, and simple persistence.

    The executor expects a `step_handler` callable with signature
    `handler(step: BuildStep) -> Any | Awaitable[Any]`. The handler may be async; the
    executor will await it when needed.
    """

    def __init__(self, storage_dir: Path = None):
        self.storage_dir = Path(storage_dir or Path.cwd() / 'data' / 'runtime')
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _state_path(self, plan: BuildPlan) -> Path:
        safe_name = plan.name.replace(' ', '_')
        return self.storage_dir / f'plan_state_{safe_name}.json'

    def _load_state(self, plan: BuildPlan) -> dict:
        p = self._state_path(plan)
        if not p.exists():
            return {"index": 0, "steps": {}}
        try:
            return json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            return {"index": 0, "steps": {}}

    def _save_state(self, plan: BuildPlan, state: dict):
        p = self._state_path(plan)
        p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')

    async def run_plan(self, plan: BuildPlan, step_handler: Callable[[BuildStep], Awaitable[Any]] | Callable[[BuildStep], Any], resume: bool = True):
        state = self._load_state(plan) if resume else {"index": 0, "steps": {}}
        start_index = int(state.get('index', 0))

        logger.info('Starting executor for plan %s at index %s', plan.name, start_index)

        for i in range(start_index, len(plan.steps)):
            step = plan.steps[i]
            sid = step.id
            step_state = state.get('steps', {}).get(sid, {})
            if step_state.get('status') == 'success':
                logger.debug('Skipping already-successful step %s', sid)
                state['index'] = i + 1
                self._save_state(plan, state)
                continue

            retries = int(getattr(step, 'retry_policy', {}).get('retries', 0))
            backoff = float(getattr(step, 'retry_policy', {}).get('backoff', 2))
            attempt = 0

            last_exc = None
            while attempt <= retries:
                try:
                    logger.info('Executing step %s (%s) attempt %s', sid, step.type, attempt + 1)
                    result = step_handler(step)
                    if asyncio.iscoroutine(result):
                        result = await result
                    # record success
                    state.setdefault('steps', {})[sid] = {
                        'status': 'success',
                        'attempts': attempt + 1,
                        'result': result,
                    }
                    state['index'] = i + 1
                    self._save_state(plan, state)
                    break
                except Exception as exc:
                    last_exc = exc
                    attempt += 1
                    logger.warning('Step %s failed on attempt %s: %s', sid, attempt, exc)
                    if attempt > retries:
                        logger.error('Step %s exhausted retries, marking failed', sid)
                        state.setdefault('steps', {})[sid] = {
                            'status': 'failed',
                            'attempts': attempt,
                            'error': str(exc),
                        }
                        state['index'] = i + 1
                        self._save_state(plan, state)
                        break
                    sleep_for = backoff ** attempt
                    logger.info('Backing off for %s seconds before retrying step %s', sleep_for, sid)
                    await asyncio.sleep(sleep_for)

            # respectful delay between steps
            try:
                delay = float(getattr(step, 'estimated_delay', 0.1) or 0.0)
            except Exception:
                delay = 0.1
            if delay:
                await asyncio.sleep(delay)

        logger.info('Plan %s execution finished', plan.name)
        return state


async def default_noop_handler(step: BuildStep):
    """A default handler used for testing: logs the step and returns a summary dict."""
    logger.info('NOOP handler executing step %s type=%s payload=%s', step.id, step.type, step.payload)
    # simulate small action time
    await asyncio.sleep(0.05)
    return {"ok": True, "id": step.id, "type": step.type.value}
                                    result = await result
