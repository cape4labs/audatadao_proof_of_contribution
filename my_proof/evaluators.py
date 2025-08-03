from typing import Literal

from psycopg import Cursor, DataError
import numpy as np
import onnxruntime
import librosa
from acoustid import compare_fingerprints, fingerprint_file
from speechmos import dnsmos


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
            "SELECT violations FROM users WHERE wallet_address=%s", (wallet_address,)
        ).fetchone()
        if violations is None:
            raise DataError(
                "Wallet address must always be present in database when running PoC."
            )

        if violations[0] == 0:
            return 1

        return 0 if violations[0] >= violation_threshold else 1

    def uniqueness(self, cur: Cursor, threshold: float = 0.8) -> Literal[0, 1]:
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
                return 0

        # The fingerprint is unique, we can insert it
        cur.execute(
            "INSERT INTO fingerprints(duration, fprint) VALUES(%s, %s)",
            (duration, fprint),
        )

        return 1

    def authenticity(self) -> Literal[0, 1]:
        session = onnxruntime.InferenceSession("model.onnx")
        input_name = session.get_inputs()[0].name

        y, sr = librosa.load(self.file_path, sr=None)

        if sr != 24000:
            y = librosa.resample(y, orig_sr=sr, target_sr=24000)

        segments = []
        max_len = 96000
        total_length = len(y)

        if total_length <= max_len:
            padded = np.zeros(max_len, dtype=np.float32)
            padded[: len(y)] = y
            segments.append(padded)
        else:
            num_chunks = total_length // max_len
            for i in range(num_chunks):
                seg = y[i * max_len : (i + 1) * max_len]
                segments.append(seg.astype(np.float32))

        probs = []

        for segment in segments:
            input_array = np.expand_dims(segment, axis=0).astype(
                np.float32
            )  # (1, 96000)
            output = session.run(None, {input_name: input_array})[0]

            e_x = np.exp(output - np.max(output, axis=1, keepdims=True))  # type: ignore
            softmax = e_x / np.sum(e_x, axis=1, keepdims=True)
            probs.append(float(softmax[0][1]))

        final_prob = float(np.mean(probs))

        print("Likely Real" if final_prob > 0.5 else "Likely Fake")
        print(f"Score: {final_prob:.4f}")

        return 1 if final_prob > 0.5 else 0

    def _pad(self, y, max_len=96000):
        x_len = y.shape[0]
        if x_len >= max_len:
            return y[:max_len]

        num_repeats = int(max_len / x_len) + 1
        padded_x = np.tile(y, num_repeats)[:max_len]
        return padded_x

    def quality(self, target_sr=16000, max_duration=660.0) -> float:
        amplitudes, _ = librosa.load(
            self.file_path, sr=target_sr
        )  # for dnsmos we need sr=16000
        signal = librosa.util.normalize(amplitudes)
        duration = librosa.get_duration(path=self.file_path)

        result = dnsmos.run(signal, sr=target_sr)
        del result["p808_mos"]  # delete P.808 metric # type: ignore

        sig_score = np.mean([float(i) for i in result.values()]) * 2 / 10  # type: ignore

        # It is not used due to the fact that we haven't decided how to score
        # audio in accordance with its duration
        duration_score = min(duration / max_duration, 1.0)

        # Apply 0.5 cutting of duration score
        resulted_quality = sig_score * (1 - (1 - duration_score) * 0.5)

        print("Quality evaluation complete:", resulted_quality)

        return float(resulted_quality)
