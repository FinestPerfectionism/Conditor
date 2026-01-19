from typing import List, Tuple
from ..planner.models import BuildPlan, BuildStep, StepType


def validate_plan(plan: BuildPlan) -> Tuple[bool, List[str]]:
    """Perform basic validation on a BuildPlan.

    Returns (ok, errors).
    """
    errors = []

    if not plan.steps:
        errors.append("Plan has no steps")
        return False, errors

    # Basic ordering checks: roles before channels, categories before channels
    seen_types = [s.type for s in plan.steps]

    # If any channel creation appears before category creation for that category, warn (best effort)
    # Simplified rule: ensure at least one CREATE_CATEGORY exists if CREATE_CHANNEL exists
    if StepType.CREATE_CHANNEL in seen_types and StepType.CREATE_CATEGORY not in seen_types:
        errors.append("Plan creates channels but no categories found")

    # Check duplicate step ids
    ids = [s.id for s in plan.steps]
    if len(ids) != len(set(ids)):
        errors.append("Duplicate step ids found")

    # Check for unknown step types
    allowed = set(item for item in StepType)
    for s in plan.steps:
        if s.type not in allowed:
            errors.append(f"Unknown step type: {s.type}")

    return (len(errors) == 0), errors


def permission_sanity_checks(plan: BuildPlan) -> Tuple[bool, List[str]]:
    """Perform lightweight permission sanity checks on a plan's payloads.

    Returns (ok, errors).
    """
    errors = []
    for s in plan.steps:
        if s.type == StepType.APPLY_PERMISSIONS:
            overwrites = s.payload.get('overwrites', [])
            for ow in overwrites:
                role = ow.get('role')
                if role == '@everyone':
                    # ensure not granting admin to everyone
                    allow = ow.get('allow', [])
                    if 'administrator' in allow:
                        errors.append('Plan attempts to grant administrator to @everyone')
    return (len(errors) == 0), errors