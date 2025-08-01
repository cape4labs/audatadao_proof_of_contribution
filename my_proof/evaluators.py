from typing import Literal

from psycopg import Cursor
import numpy as np
# import torch
import librosa
import yaml
from acoustid import compare_fingerprints, fingerprint_file
from speechmos import dnsmos

# from my_proof.model.model import RawNet

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
            "SELECT violations FROM users WHERE wallet_address=%s",
            (wallet_address,)).fetchone()
        if violations is None:
            cur.execute("INSERT INTO users(wallet_address) VALUES(%s)", (wallet_address,))
            return 1

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
            (duration, fprint))

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
