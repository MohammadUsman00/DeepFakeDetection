from __future__ import annotations

from app.ml.result_decision import predicted_manipulation


def test_none_when_low_confidence() -> None:
    assert predicted_manipulation(final_score=0.99, low_confidence=True, threshold=0.5) is None


def test_none_when_no_score() -> None:
    assert predicted_manipulation(final_score=None, low_confidence=False, threshold=0.5) is None


def test_true_at_threshold() -> None:
    assert predicted_manipulation(final_score=0.5, low_confidence=False, threshold=0.5) is True


def test_false_below_threshold() -> None:
    assert predicted_manipulation(final_score=0.49, low_confidence=False, threshold=0.5) is False


def test_custom_threshold() -> None:
    assert predicted_manipulation(final_score=0.6, low_confidence=False, threshold=0.7) is False
    assert predicted_manipulation(final_score=0.71, low_confidence=False, threshold=0.7) is True
