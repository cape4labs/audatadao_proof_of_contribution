import logging
from typing import Any
import os
import json
from psycopg import connect

from my_proof.models import ProofResponse
from my_proof.evaluators import ParameterEvaluator


class Proof:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.proof_response = ProofResponse(dlp_id=config["dlp_id"])

    def generate(self) -> ProofResponse:
        """Generate proofs for all input files."""
        logging.info("Starting proof generation")

        for input_filename in os.listdir(self.config["input_dir"]):
            input_file = os.path.join(self.config["input_dir"], input_filename)
            ext = os.path.splitext(input_file)[1].lower()
            if ext == ".ogg":
                file_path = input_file
            elif ext == ".json":
                with open(input_file, "r") as f:
                    input_data = json.load(f)
                    user_wallet_address = input_data["user"]["wallet_address"]

        if not file_path or not user_wallet_address:
            print(os.listdir(self.config["input_dir"]))

        # Evaluate parameters
        evaluator = ParameterEvaluator(self.config, file_path)

        with connect(self.config["db_uri"]) as conn:
            with conn.cursor() as cur:
                try:
                    self.proof_response.uniqueness = evaluator.uniqueness(cur)
                    self.proof_response.ownership = evaluator.ownership(
                        cur, user_wallet_address
                    )
                except Exception:
                    conn.rollback()
                    raise
            conn.commit()

        # Run the most expensive operations only after operations with network
        # (which may have network interruptions) access are done
        self.proof_response.authenticity = evaluator.authenticity()
        self.proof_response.quality = evaluator.quality()

        # Check validity
        self.proof_response.valid = (
            self.proof_response.ownership == 1
            and self.proof_response.uniqueness == 1
            and self.proof_response.authenticity == 1
            and (self.proof_response.quality > 0.1)
        )

        # Calculate overall score and validity
        self.proof_response.score = (
            0.6 * self.proof_response.quality + 0.4 * self.proof_response.ownership
        )

        # Additional (public) properties to include in the proof about the data
        self.proof_response.attributes = {
            "total_score": 1,
            "score_threshold": 0.5,
        }

        # Additional metadata about the proof, written onchain
        self.proof_response.metadata = {
            "dlp_id": self.config["dlp_id"],
        }

        return self.proof_response
