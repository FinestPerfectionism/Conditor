"""planner package: compiler that turns `ServerSpec` into `BuildPlan`.

Public API:
- `compile_spec_to_plan(spec)`
"""

from .models import BuildPlan, BuildStep, StepType

# `compiler` historically exported `compile_from_files` in older versions.
# Import it if available to remain backward compatible with older deployments
# or external callers that expect the symbol.
from .compiler import compile_spec_to_plan

try:
	from .compiler import compile_from_files  # type: ignore
	__all__ = ["BuildPlan", "BuildStep", "StepType", "compile_spec_to_plan", "compile_from_files"]
except Exception:
	__all__ = ["BuildPlan", "BuildStep", "StepType", "compile_spec_to_plan"]
