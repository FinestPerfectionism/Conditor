from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

class StepType(Enum):
    CREATE_ROLE = 'create_role'
    CREATE_CATEGORY = 'create_category'
    CREATE_CHANNEL = 'create_channel'
    APPLY_PERMISSIONS = 'apply_permissions'
    POST_MESSAGE = 'post_message'
    REGISTER_METADATA = 'register_metadata'

@dataclass
class BuildStep:
    id: str
    type: StepType
    payload: Dict[str, Any] = field(default_factory=dict)
    retry_policy: Dict[str, Any] = field(default_factory=lambda: {"retries": 3, "backoff": 2})
    estimated_delay: float = 0.5  # seconds suggested between steps

@dataclass
class BuildPlan:
    name: str
    steps: List[BuildStep] = field(default_factory=list)

    def add_step(self, step: BuildStep):
        self.steps.append(step)

    def to_dict(self):
        return {
            "name": self.name,
            "steps": [
                {
                    "id": s.id,
                    "type": s.type.value,
                    "payload": s.payload,
                    "retry_policy": s.retry_policy,
                    "estimated_delay": s.estimated_delay,
                }
                for s in self.steps
            ],
        }
