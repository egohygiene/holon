"""Holon materialization engine public surface."""

from .common import MaterializationError, STATE_RELATIVE_PATH
from .continuity import (
    STATE_RELATIVE_PATH as CONTINUITY_STATE_RELATIVE_PATH,
    apply_continuity_plan,
    build_continuity_plan,
    rollback_continuity_target,
    validate_continuity_plan,
    validate_continuity_request,
    verify_continuity_target,
)
from .engine import build_plan, render_plan, rollback_target, verify_target

__all__ = [
    "MaterializationError",
    "STATE_RELATIVE_PATH",
    "CONTINUITY_STATE_RELATIVE_PATH",
    "apply_continuity_plan",
    "build_plan",
    "build_continuity_plan",
    "render_plan",
    "rollback_continuity_target",
    "rollback_target",
    "validate_continuity_plan",
    "validate_continuity_request",
    "verify_continuity_target",
    "verify_target",
]
