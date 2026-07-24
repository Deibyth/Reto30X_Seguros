"""AudioDecisionEngine — rules + variability for TTS audio decisions.

Three-layer decision system:
1. HARD NEVER rules — URLs, phones, emails, short confirmations, errors → no audio
2. STRONG SIGNALS — greetings, user sent audio, product question → audio
3. VARIABILITY — borderline cases use ~60% probability for natural variability
"""

import logging
import random
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Patterns that ALWAYS prevent audio
_NEVER_PATTERNS: list[re.Pattern] = [
    re.compile(r"https?://\S+", re.IGNORECASE),
    re.compile(r"\b\d{7,}\b"),  # phone-like numbers (7+ digits)
    re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.+-]+\b"),  # email
]

# Responses under this length and ending with punctuation skip audio
_NEVER_SHORT_MAX = 65

VARIABILITY_PROBABILITY = 0.6  # ~60% chance for borderline cases


@dataclass
class AudioContext:
    """Context for audio decision.

    Attributes
    ----------
    is_greeting : bool
        True if this is Anna's first interaction with the user.
    user_sent_audio : bool
        True if the user's last message was audio (not text).
    product_mentioned : bool
        True if the response mentions a specific insurance product.
    text_length : int
        Length of the response text in characters.
    """

    is_greeting: bool = False
    user_sent_audio: bool = False
    product_mentioned: bool = False
    text_length: int = 0


class AudioDecisionEngine:
    """Decide whether a response should be delivered as audio."""

    @staticmethod
    def should_send_audio(text: str, context: AudioContext) -> bool:
        """Return True if the response should be delivered as audio."""

        # ── Layer 1: HARD NEVER ────────────────────────────────────────
        if any(pattern.search(text) for pattern in _NEVER_PATTERNS):
            logger.debug("Audio decision: NEVER rule matched")
            return False

        # ── Layer 2: STRONG SIGNALS ────────────────────────────────────
        if context.is_greeting:
            logger.debug("Audio decision: strong signal — greeting")
            return True

        if context.user_sent_audio:
            logger.debug("Audio decision: strong signal — user sent audio")
            return True

        if context.product_mentioned and context.text_length >= 80:
            logger.debug("Audio decision: strong signal — product explanation")
            return True

        # ── Short-text guard (after strong signals) ────────────────────
        # Very short texts (<50 chars) never get audio — too short to matter
        if context.text_length < 50:
            return False

        # ── Layer 3: VARIABILITY ───────────────────────────────────────
        if context.text_length > 200:
            roll = random.random() < VARIABILITY_PROBABILITY
            logger.debug("Audio decision: variability (>200 chars) — roll=%s", roll)
            return roll

        # Default: no audio
        return False
