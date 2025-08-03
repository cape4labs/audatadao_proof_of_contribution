def test_ownership(cur, default_evs):
    violations = 5
    cur.execute(
        """INSERT INTO users(violations, wallet_address)
        VALUES (0, 'test1'), (%s, 'test2')""",
        (violations,),
    )

    assert 1 == default_evs[0].ownership(cur, "test1")
    assert 0 == default_evs[1].ownership(cur, "test2", violation_threshold=violations)


def test_uniqueness(cur, default_evs):
    assert 1 == default_evs[0].uniqueness(cur)
    assert 0 == default_evs[0].uniqueness(cur)
    assert 1 == default_evs[1].uniqueness(cur)
    assert 0 == default_evs[1].uniqueness(cur)


def test_quality(default_evs):
    assert 0 < default_evs[0].quality() < 1


def test_authenticity(default_evs):
    assert 1 == default_evs[0].authenticity()
    assert 0 == default_evs[2].authenticity()
