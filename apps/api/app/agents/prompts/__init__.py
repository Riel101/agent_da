"""Versioned prompts. Bump ``VERSION`` whenever the text changes."""

from app.agents.prompts.critique_v1 import VERSION as CRITIQUE_VERSION
from app.agents.prompts.intake_v1 import VERSION as INTAKE_VERSION
from app.agents.prompts.motivation_v1 import VERSION as MOTIVATION_VERSION
from app.agents.prompts.plan_v1 import VERSION as PLAN_VERSION
from app.agents.prompts.todos_v1 import VERSION as TODOS_VERSION

#: Recorded on every draft so a generated plan can be traced to its prompt set.
PROMPT_SET_VERSION = "|".join(
    [INTAKE_VERSION, PLAN_VERSION, CRITIQUE_VERSION, TODOS_VERSION, MOTIVATION_VERSION]
)

__all__ = ["PROMPT_SET_VERSION"]
