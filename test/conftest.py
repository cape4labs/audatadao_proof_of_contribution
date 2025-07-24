import pytest
from sqlalchemy import create_engine

from my_proof.models import metadata_obj
from my_proof.__main__ import load_config


@pytest.fixture
def conn():
    engine = create_engine("postgresql+psycopg://postgres:root@localhost/audata")
    with engine.connect() as conn:
        metadata_obj.create_all(conn)
        conn.commit()
        yield conn
        # Don't commit here in order to prevent test data from saving


@pytest.fixture
def config():
    config = load_config()
    return config
