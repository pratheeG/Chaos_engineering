"""Human feedback node — interrupt point that waits for user input."""

from __future__ import annotations

from graph.state import ChaosState


def human_feedback_node(state: ChaosState) -> dict:
    """Pause point for human feedback.

    The graph interrupts BEFORE this node. When resumed it resets routing
    back to the supervisor so it can re-evaluate the user's reply.
    """
    return {"next_agent": "supervisor"}
