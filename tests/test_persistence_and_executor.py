import asyncio
from pathlib import Path
import tempfile
import json

import pytest

from src.conditor.core.planner.models import BuildPlan, BuildStep, StepType
from src.conditor.core.executor.worker import Executor, default_noop_handler
from src.conditor.core.persistence.backup import export_plan, import_plan


def make_sample_plan():
    plan = BuildPlan(name='test-plan')
    plan.add_step(BuildStep(id='r1', type=StepType.CREATE_ROLE, payload={'name': 'Tester'}, estimated_delay=0.0))
    plan.add_step(BuildStep(id='c1', type=StepType.CREATE_CATEGORY, payload={'name': 'Community'}, estimated_delay=0.0))
    plan.add_step(BuildStep(id='ch1', type=StepType.CREATE_CHANNEL, payload={'name': 'general', 'category': 'Community'}, estimated_delay=0.0))
    plan.add_step(BuildStep(id='m1', type=StepType.POST_MESSAGE, payload={'channel': 'general', 'content': 'Hello world'}, estimated_delay=0.0))
    return plan


def test_export_import_plan(tmp_path: Path):
    plan = make_sample_plan()
    p = tmp_path / 'plan.json'
    export_plan(plan, p)
    assert p.exists()
    imported = import_plan(p)
    assert isinstance(imported, BuildPlan)
    assert len(imported.steps) == len(plan.steps)


@pytest.mark.asyncio
async def test_executor_noop_runs():
    plan = make_sample_plan()
    executor = Executor(storage_dir=Path(tempfile.gettempdir()) / 'conditor_test_runtime')
    state = await executor.run_plan(plan, default_noop_handler, resume=False)
    assert state.get('steps')
    successes = sum(1 for s in state.get('steps', {}).values() if s.get('status') == 'success')
    assert successes == len(plan.steps)
