"""TranscriptParser — deterministic parsing of a raw transcript into turns.

No LLM. Recognizes speaker-labelled lines ("Cliente:", "Agente:", "Vendedor:",
"Client:", "Agent:", ...) and markdown turn headers ("### Turno 1 — Asesor"),
then groups multi-line content under the current speaker. This is the entry
to the Evidence layer.
"""

import logging
import re

from prosales.engines.evidence.models import EvidenceSource, EvidenceTurn

logger = logging.getLogger(__name__)

# Label -> normalized speaker. Matched case-insensitively.
_AGENT_LABELS = {"agente", "agent", "vendedor", "asesor", "seller", "rep", "representante"}
_CLIENT_LABELS = {"cliente", "client", "customer", "comprador", "prospecto", "lead", "usuario", "user"}

_LABEL_RE = re.compile(r"^\s*([A-Za-zÁÉÍÓÚÑáéíóúñ ]{1,30})\s*:\s*(.*)$")
# e.g. "### Turno 1 — Asesor" / "Turno 2 - Cliente"
_TURN_HEADER_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?turno\s+\d+\s*[—–\-:]+\s*([A-Za-zÁÉÍÓÚÑáéíóúñ ]{1,30})\s*$",
    re.IGNORECASE,
)


def _normalize_speaker(label: str) -> str | None:
    key = label.strip().lower()
    if key in _AGENT_LABELS:
        return "agent"
    if key in _CLIENT_LABELS:
        return "client"
    return None


class TranscriptParser:
    """Parse a ``Cliente:``/``Agente:`` style transcript into ordered turns."""

    def parse(self, transcript: str) -> list[EvidenceTurn]:
        turns: list[EvidenceTurn] = []
        current_speaker: str | None = None
        current_lines: list[str] = []

        def flush() -> None:
            nonlocal current_lines
            if current_speaker is not None and current_lines:
                text = " ".join(line.strip() for line in current_lines if line.strip()).strip()
                if text:
                    turns.append(
                        EvidenceTurn(turn_index=len(turns), speaker=current_speaker, text=text)
                    )
            current_lines = []

        for raw_line in (transcript or "").splitlines():
            line = raw_line.strip()
            match = _LABEL_RE.match(raw_line)
            speaker = _normalize_speaker(match.group(1)) if match else None
            remainder = match.group(2).strip() if match else ""

            if speaker is None:
                header = _TURN_HEADER_RE.match(line)
                if header:
                    speaker = _normalize_speaker(header.group(1))
                    remainder = ""

            if speaker is None and line:
                # Standalone label line, no colon — e.g. a bare "CLIENTE" line
                # followed by its text on the next lines (common when a
                # transcript is copy-pasted from a doc/chat export).
                standalone = _normalize_speaker(line)
                if standalone:
                    speaker = standalone
                    remainder = ""

            if speaker is not None:
                # New labelled turn: close the previous one.
                flush()
                current_speaker = speaker
                current_lines = [remainder] if remainder else []
            elif raw_line.strip():
                # Continuation of the current speaker.
                current_lines.append(raw_line)

        flush()
        if not turns and (transcript or "").strip():
            logger.warning(
                "TranscriptParser produced 0 turns from %d chars; "
                "need 'Cliente:'/'Agente:' lines or '### Turno N — Asesor' headers",
                len(transcript),
            )
        return turns

    def to_source(self, transcript: str, **source_kwargs) -> EvidenceSource:
        """Parse and wrap turns into an EvidenceSource DTO."""
        return EvidenceSource(turns=self.parse(transcript), **source_kwargs)
