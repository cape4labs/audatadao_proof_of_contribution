from uuid import uuid4
from typing import Dict, Optional, Any

from pydantic import BaseModel

import sqlalchemy
from sqlalchemy.orm import declarative_base


class ProofResponse(BaseModel):
    """
    Represents the response of a proof of contribution. Only the score and metadata will be written onchain, the rest of the proof lives offchain.

    Onchain attributes - these are written to the data registry:
        score: A score between 0 and 1 for the file, used to determine how valuable the file is. This can be an aggregation of the individual scores below.
        metadata: Additional metadata about the proof

    Offchain attributes - the remainder of the proof is written to IPFS
        dlp_id: The DLP ID is found in the DLP Root Network contract after the DLP is registered.
        valid: A single boolean to summarize if the file is considered valid in this DLP.
        authenticity: A score between 0 and 1 to rate if the file has been tampered with.
        ownership: A score between 0 and 1 to verify the ownership of the file.
        quality: A score between 0 and 1 to show the quality of the file
        uniqueness: A score between 0 and 1 to show unique the file is, compared to others in the DLP.
        attributes: Custom attributes added to the proof to provide extra context about the encrypted file.
    """

    dlp_id: int
    valid: bool = False
    score: float = 0.0
    authenticity: float = 0.0
    ownership: float = 0.0
    quality: float = 0.0
    uniqueness: float = 0.0
    attributes: Optional[Dict[str, Any]] = {}
    metadata: Optional[Dict[str, Any]] = {}


Base = declarative_base()


class Users(Base):
    __tablename__ = "users"

    id = sqlalchemy.Column(sqlalchemy.UUID, default=uuid4(), primary_key=True)
    # Count failed authenticity checks to ban users who exceeds limit
    failed_authenticity_count = sqlalchemy.Column(sqlalchemy.Integer, default=0)
    is_banned = sqlalchemy.Column(sqlalchemy.Boolean, default=False)
    # Use server-side timestamp to ensure consistency across time zones and avoid app-server clock drift
    uploaded_at = sqlalchemy.Column(
        sqlalchemy.DateTime(timezone=True), server_default=sqlalchemy.func.now()
    )


class Contributions(Base):
    __tablename__ = "contributions"

    id = sqlalchemy.Column(
        sqlalchemy.UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    owner_id = sqlalchemy.Column(
        sqlalchemy.UUID(as_uuid=True), sqlalchemy.ForeignKey("users.id")
    )
    # Store duration for accurate fingerprint comparisons
    duration = sqlalchemy.Column(sqlalchemy.Float, nullable=False)
    uploaded_at = sqlalchemy.Column(
        sqlalchemy.DateTime(timezone=True), server_default=sqlalchemy.func.now()
    )
    file_link = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    file_link_hash = sqlalchemy.Column(
        sqlalchemy.String(32), unique=True, nullable=False
    )  # 32 chars for md5
    # Technically, the same fingerprint can be written
    # in database because if we add parameter "unique=True"
    # here, the value will be too long to be handled as unique
    # by PostgreSQL. Also, when a fingerprint is stored in PostgreSQL
    # it's converted into raw bytes, so it's required to decode them
    # before using
    fingerprint = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    # Store hash for fast uniquness lookups.
    fingerprint_hash = sqlalchemy.Column(
        sqlalchemy.String(32), unique=True, nullable=False
    )  # 32 chars for md5
