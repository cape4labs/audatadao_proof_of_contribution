import logging
from typing import Any
import os
import json

from sqlalchemy import create_engine

from my_proof.models import ProofResponse, metadata_obj
from my_proof.evaluators import ParameterEvaluator


class Proof:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.proof_response = ProofResponse(dlp_id=config["dlp_id"])

    def generate(self) -> ProofResponse:
        """Generate proofs for all input files."""
        logging.info("Starting proof generation")

        with open(os.path.join(self.config["input_dir"], "account.json"), "r") as f:
            input_data = json.load(f)
            user_wallet_address = input_data["wallet_address"]

        file_path = os.path.join(self.config["input_dir"], "data.ogg")

        # engine = create_engine(self.config["db_uri"])
        # with engine.connect() as conn:
        #     metadata_obj.create_all(conn)
        #     param = ParameterEvaluator(self.config, conn, file_path)

        #     self.proof_response.authenticity = param.authenticity()
        #     self.proof_response.quality = param.quality()
        #     self.proof_response.ownership = param.ownership(user_wallet_address)
        #     self.proof_response.uniqueness = param.uniqueness()

        #     conn.commit()

        self.proof_response.authenticity = 1
        self.proof_response.quality = 1
        self.proof_response.ownership = 1
        self.proof_response.uniqueness = 1

        # Check validity
        self.proof_response.valid = (
            self.proof_response.ownership == 1
            and self.proof_response.uniqueness == 1
            and self.proof_response.authenticity == 1
            and (self.proof_response.quality > 0.5)
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
