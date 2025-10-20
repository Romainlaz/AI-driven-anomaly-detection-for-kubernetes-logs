# Pipeline/normalizer.py
import re

class Normalizer:
    """Basic text normalizer with PII redaction."""

    EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}")
    DIGIT_RE = re.compile(r"\d+")

    def normalize(self, message: str) -> str:
        msg = self.EMAIL_RE.sub("<EMAIL>", message)
        msg = self.DIGIT_RE.sub("<NUM>", msg)
        return msg.strip().lower()
