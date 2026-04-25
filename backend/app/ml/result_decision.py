"""Shared policy for binary manipulation label from final_score (configurable threshold)."""

from __future__ import annotations


def predicted_manipulation(
    *,
    final_score: float | None,
    low_confidence: bool,
    threshold: float,
) -> bool | None:
    """
    When evidence is too weak (low_confidence) or score is missing, return None.
    Otherwise return whether p_fake is at/above the deployment decision threshold.
    """
    if low_confidence or final_score is None:
        return None
    return float(final_score) >= float(threshold)
