from hashlib import md5
from typing import Literal

import numpy as np

import torch
import librosa
import yaml
from acoustid import compare_fingerprints, fingerprint_file
from speechmos import dnsmos
from sqlalchemy.exc import NoResultFound
from sqlalchemy import Connection, insert, select


# from my_proof.model.model import RawNet
from my_proof.models import fingerprints, users


class ParameterEvaluator:
    def __init__(self, config: dict, conn: Connection, file_path: str):
        self.conn = conn
        self.config = config
        self.file_path = file_path

    def ownership(self, user_email: str, violation_threshold: int = 5) -> Literal[0, 1]:
        """
        A user is considered to pass ownership test unless they have been banned.
        If the user doesn't exist, they're initialized and granted ownership.
        """
        try:
            violations = self.conn.execute(
                select(users.c.violations).where(users.c.email == user_email)
            ).one()[0]
        except NoResultFound:
            self.conn.execute(insert(users).values(email=user_email))
            return 1

        if violations is None:
            return 1

        return 0 if violations >= violation_threshold else 1

    def uniqueness(self, threshold: float = 0.8, yield_per: int = 100) -> Literal[0, 1]:
        """
        yield_per: amount of entities loaded into memory while comparing fingerprints.
        """

        if not 0.0 <= threshold <= 1.0:
            raise ValueError("similarity_threshold must be between 0.0 and 1.0")

        if yield_per < 1:
            raise ValueError("yield_per must be >= 1")

        # Get fingerprint, duration, and hash
        duration, fprint = fingerprint_file(self.file_path)
        fprint_hash = md5(str(fprint).encode()).hexdigest()

        # Check for exactly the same one
        try:
            self.conn.execute(
                select(fingerprints).where(fingerprints.c.fprint_hash == fprint_hash)
            ).one()
            return 0
        except NoResultFound:
            pass

        db_fprints = self.conn.execute(
            select(fingerprints.c.duration, fingerprints.c.fprint)
        )
        # Loop through db fingerprints and compare for similarity
        # Use yield_per to avoid loading all db in memory
        for db_duration, db_fprint in db_fprints.yield_per(yield_per):
            # Decode db fingerprint
            decoded_db_fprint = bytes.fromhex(db_fprint[2:])

            # Provide arguments in format (duration, fingerprint)
            # `similarity_score` is between 0.0 and 1.0
            similarity_score = compare_fingerprints(
                (duration, fprint),
                (db_duration, decoded_db_fprint),
            )
            if similarity_score >= threshold:
                return 0

        # The fingerprint is unique, we can insert it
        self.conn.execute(insert(fingerprints).values(duration=duration, fprint=fprint, fprint_hash=fprint_hash))

        return 1

    def authenticity(self) -> Literal[0, 1]:
        with open(self.config["path_to_yaml"], "r") as f:
            custom_config = yaml.safe_load(f)

        device = torch.device("cpu")

        model = RawNet(custom_config["model"], device=device)
        model.load_state_dict(
            torch.load(
                self.config["path_to_model"], map_location="cpu", weights_only=False
            )
        )
        model.eval()
        model = model.to(device)

        y, sr = librosa.load(self.file_path, sr=None)

        if sr != 24000:
            y = librosa.resample(y, orig_sr=sr, target_sr=24000)

        segments = []
        max_len = 96000
        total_len = len(y)

        if total_len <= max_len:
            y_pad = self._pad(y, max_len)
            segments.append(torch.tensor(y_pad, dtype=torch.float32))
        else:
            num_chunks = total_len // max_len
            for i in range(num_chunks):
                seg = y[i * max_len : (i + 1) * max_len]
                segments.append(
                    torch.tensor(self._pad(seg, max_len), dtype=torch.float32)
                )

        model.eval()
        probs = []
        with torch.no_grad():
            for segment in segments:
                input_tensor = segment.unsqueeze(0).to(device)
                output = model(input_tensor)
                if isinstance(output, tuple):
                    output = output[0]
                softmax_out = torch.softmax(output, dim=1)[0][1].item()
                probs.append(softmax_out)

        final_prob = float(np.mean(probs))
        print("Likely Real" if final_prob > 0.5 else "Likely Fake")
        print(f"Score: {final_prob}")
        return 1 if final_prob > 0.5 else 0

    def _pad(self, y, max_len=96000):
        x_len = y.shape[0]
        if x_len >= max_len:
            return y[:max_len]

        num_repeats = int(max_len / x_len) + 1
        padded_x = np.tile(y, num_repeats)[:max_len]
        return padded_x

    def quality(self, target_sr=16000, max_duration=120.0):
        amplitudes, _ = librosa.load(
            self.file_path, sr=target_sr
        )  # for dnsmos we need sr=16000
        signal = librosa.util.normalize(amplitudes)

        result = dnsmos.run(signal, sr=target_sr)
        del result["p808_mos"]  # delete P.808 metric # type: ignore

        sig_score = np.mean([float(i) for i in result.values()]) * 2 / 10  # type: ignore

        # It is not used due to the fact that we haven't decided how to score
        # audio in accordance with its duration
        # duration_score = min(duration / max_duration, 1.0)

        print("Quality evaluation complete:", sig_score)

        return sig_score
