from datetime import datetime, timedelta, timezone

from app.memory.retrieval import _cosine_similarity, _recency_score


def test_cosine_similarity_identical_vectors_is_one():
    v = [1.0, 0.0, 0.0]
    assert _cosine_similarity(v, v) == 1.0


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_similarity_handles_empty_or_mismatched_vectors():
    assert _cosine_similarity([], [1.0]) == 0.0
    assert _cosine_similarity([1.0, 2.0], [1.0]) == 0.0


def test_recency_score_decays_with_age():
    now = datetime.now(timezone.utc)
    fresh = _recency_score(now)
    old = _recency_score(now - timedelta(hours=72))  # exatamente uma half-life
    very_old = _recency_score(now - timedelta(days=30))

    assert fresh > old > very_old
    assert 0.45 < old < 0.55  # ~0.5 após uma half-life
