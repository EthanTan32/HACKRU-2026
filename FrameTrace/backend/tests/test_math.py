from app.detectors.text import levenshtein
from app.detectors.common import robust_index


def test_levenshtein():
    assert levenshtein('ABC123', 'ABC128') == 1
    assert levenshtein('', 'XYZ') == 3
    assert levenshtein('SAME', 'SAME') == 0


def test_robust_index():
    assert robust_index([0, 5, 10], 10) == .5
    assert robust_index([], 10) is None
