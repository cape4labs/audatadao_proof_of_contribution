from typing import Literal

from psycopg import Cursor, DataError
from acoustid import compare_fingerprints, fingerprint_file


class ParameterEvaluator:
    def __init__(self, config: dict, file_path: str):
        self.config = config
        self.file_path = file_path

    def ownership(
        self, cur: Cursor, wallet_address: str, violation_threshold: int = 5
    ) -> Literal[0, 1]:
        """
        A user is considered to pass ownership test unless they have been banned.
        If the user doesn't exist, they're initialized and granted ownership.
        """

        violations = cur.execute(
            "SELECT violations FROM users WHERE address=%s", (wallet_address,)
        ).fetchone()
        if violations is None:
            raise DataError(
                "Wallet address must always be present in database when running PoC."
            )

        if violations[0] == 0:
            return 1

        return 0 if violations[0] >= violation_threshold else 1

    def uniqueness(self, cur: Cursor, threshold: float = 0.8) -> tuple:
        """
        yield_per: amount of entities loaded into memory while comparing fingerprints.
        """

        if not 0.0 <= threshold <= 1.0:
            raise ValueError("similarity_threshold must be between 0.0 and 1.0")

        # Get fingerprint and duration
        duration, fprint = fingerprint_file(self.file_path)

        cur.execute("SELECT duration, fprint FROM fingerprints")
        # Loop through db fingerprints and compare for similarity
        # Use yield_per to avoid loading all db in memory
        for db_duration, db_fprint in cur:
            # Decode db fingerprint
            # Provide arguments in format (duration, fingerprint)
            # `similarity_score` is between 0.0 and 1.0
            similarity_score = compare_fingerprints(
                (duration, fprint),
                (db_duration, db_fprint),
            )
            if similarity_score >= threshold:
                return 0, 0, 0

        return 1, duration, fprint
