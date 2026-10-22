import itertools

from laf import outcome_training as O


def test_transform_identity_shift_and_spread():
    q = [0, 0, 1, 2, 4, 7, 12, 16, 20]
    assert O.transform([float(x) for x in q], 1.0, 1.0) == q
    up = O.transform([float(x) for x in q], 2.0, 1.0)
    assert up[4] == 9 and all(a <= b for a, b in itertools.pairwise(up))
    wide = O.transform([float(x) for x in q], 1.0, 2.0)
    assert wide[4] == 4 and wide[-1] > q[-1] and wide[0] == 0
