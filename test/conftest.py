import os
import pytest
import psycopg

from my_proof.__main__ import load_config
from my_proof.evaluators import ParameterEvaluator


@pytest.fixture
def cur():
    test_db_uri = os.getenv(
        "TEST_DB_URI", "postgresql://postgres:root@localhost/audata"
    )
    with psycopg.connect(test_db_uri, autocommit=False) as conn:
        with conn.cursor() as cur:
            yield cur
            # Prevent data from being saved; with psycopg3 you should do that explicitly
            conn.rollback()


@pytest.fixture
def config():
    config = load_config()
    return config


@pytest.fixture
def default_evs(config):
    ev0 = ParameterEvaluator(config, "test/data/real0.ogg")
    ev1 = ParameterEvaluator(config, "test/data/real1.ogg")
    ev2 = ParameterEvaluator(config, "test/data/generated_by_ai0.ogg")
    return [ev0, ev1, ev2]
