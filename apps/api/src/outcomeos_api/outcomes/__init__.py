"""Outcome verification domain."""

from .state_machine import OutcomeState, OutcomeTransition, transition_outcome

__all__ = ["OutcomeState", "OutcomeTransition", "transition_outcome"]
