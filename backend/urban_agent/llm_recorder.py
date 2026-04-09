"""
Lightweight LLM interaction recorder shared across agents.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


def _strip_code_fence(payload: str) -> str:
    """Extract inner block from fenced code snippets if present."""
    text = payload.strip()
    if "```json" in text:
        try:
            return text.split("```json", 1)[1].split("```", 1)[0]
        except IndexError:
            return text
    if "```" in text:
        try:
            return text.split("```", 1)[1].split("```", 1)[0]
        except IndexError:
            return text
    return text


def _serialize_messages(prompt: str) -> str:
    """Utility passthrough to keep API flexible."""
    return prompt


@dataclass
class LLMRecorder:
    """Tracks prompt/response pairs and stores them on disk."""

    log_path: Optional[Path] = None
    verbose_log_path: Optional[Path] = None
    session_timestamp: Optional[str] = None
    interactions: List[Dict[str, object]] = field(default_factory=list)

    def start_session(self, output_dir: Path) -> None:
        """Reset state and bind to a new output directory."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        self.session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = output_dir / f"llm_interactions_{self.session_timestamp}.json"
        self.verbose_log_path = output_dir / f"llm_verbose_log_{self.session_timestamp}.txt"
        self.interactions.clear()
        if self.verbose_log_path:
            with open(self.verbose_log_path, "w", encoding="utf-8") as handle:
                handle.write(
                    f"LLM Verbose Log - Session {self.session_timestamp}\n"
                    f"{'='*80}\n"
                )

    def record(
        self,
        stage: str,
        prompt: str,
        response: str,
        elapsed_time: float,
        metadata: Optional[Dict[str, object]] = None,
    ) -> None:
        """Persist a single LLM exchange."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "stage": stage,
            "prompt": _serialize_messages(prompt),
            "response": response,
            "elapsed_time": elapsed_time,
            "prompt_length": len(prompt),
            "response_length": len(response),
            "metadata": metadata or {},
        }
        self.interactions.append(entry)
        self._flush()
        self._write_verbose_log(entry)

    def _flush(self) -> None:
        if not self.log_path:
            return
        data = {
            "session_info": {
                "timestamp": self.session_timestamp,
                "total_interactions": len(self.interactions),
                "total_time": sum(i["elapsed_time"] for i in self.interactions),
            },
            "interactions": self.interactions,
        }
        with open(self.log_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)

    def get_log_file(self) -> Optional[str]:
        return str(self.log_path) if self.log_path else None

    def get_text_log_file(self) -> Optional[str]:
        return str(self.verbose_log_path) if self.verbose_log_path else None

    def get_interactions(self) -> List[Dict[str, object]]:
        return list(self.interactions)

    def _write_verbose_log(self, entry: Dict[str, object]) -> None:
        if not self.verbose_log_path:
            return
        prompt = entry.get("prompt", "")
        response = entry.get("response", "")
        reasoning = self._extract_reasoning(response)
        with open(self.verbose_log_path, "a", encoding="utf-8") as handle:
            handle.write(
                f"\n[Stage] {entry.get('stage')} @ {entry.get('timestamp')}\n"
                f"[Prompt]\n{prompt}\n"
            )
            handle.write("[Inference]\n")
            handle.write(f"{reasoning if reasoning else 'N/A'}\n")
            handle.write("[Response]\n")
            handle.write(f"{response}\n")
            handle.write("-" * 80 + "\n")

    def _extract_reasoning(self, response_text: str) -> Optional[str]:
        """Try to extract explicit reasoning field from JSON responses."""
        candidate = _strip_code_fence(response_text)
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                reasoning = data.get("reasoning")
                if isinstance(reasoning, str):
                    return reasoning
        except json.JSONDecodeError:
            return None
        return None

