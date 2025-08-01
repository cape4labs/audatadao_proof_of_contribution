from my_proof.evaluators import ParameterEvaluator

def test_ownership(cur, config):
    evaluator = ParameterEvaluator(config, "")
    result = evaluator.ownership(cur, "test_wallet_address1")
    assert result == 1

    cur.execute(
        "INSERT INTO users(violations, wallet_address) VALUES(5, 'test_wallet_address2')"
    )

    result = evaluator.ownership(cur, "test_wallet_address2", violation_threshold=5)
    assert result == 0


def test_uniqueness(cur, config):
    evaluator = ParameterEvaluator(config, "test/data/1.ogg")
    result = evaluator.uniqueness(cur)
    assert result == 1

    evaluator = ParameterEvaluator(config, "test/data/1.ogg")
    result = evaluator.uniqueness(cur)
    assert result == 0

    evaluator = ParameterEvaluator(config, "test/data/2.ogg")
    result = evaluator.uniqueness(cur)
    assert result == 1

    # Same as 1.ogg
    evaluator = ParameterEvaluator(config, "test/data/3.ogg")
    result = evaluator.uniqueness(cur)
    assert result == 0
