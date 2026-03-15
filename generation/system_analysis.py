"""AI-system risk analysis grounded in retrieved legal context."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import json
import re
from typing import Sequence

from generation.llm import LLMDependencyError, LLMSettings, LiteLLMClient
from generation.prompt import build_citation_label, build_context_block
from retrieval.retriever import HybridRetriever, RetrievalHit, RetrievalResult

RISK_LEVELS = {
    "prohibited": "prohibited",
    "unacceptable": "prohibited",
    "unacceptable_risk": "prohibited",
    "high": "high",
    "high_risk": "high",
    "limited": "limited",
    "limited_risk": "limited",
    "minimal": "minimal",
    "minimal_risk": "minimal",
    "general_purpose": "general_purpose",
    "general-purpose": "general_purpose",
    "general purpose": "general_purpose",
    "gpai": "general_purpose",
    "unclear": "unclear",
    "unknown": "unclear",
}


@dataclass(slots=True)
class AISystemAnalysisResult:
    level_of_risk: str
    confidence: int
    summary: str
    citations: list[str]
    low_confidence: bool


class AISystemAnalyzer:
    """Classify an AI system using retrieved AI Act context and an LLM."""

    def __init__(
        self,
        retriever: HybridRetriever,
        *,
        default_llm_settings: LLMSettings | None = None,
    ) -> None:
        self.retriever = retriever
        self.default_llm_settings = default_llm_settings or LLMSettings.from_env()

    def analyze(
        self,
        *,
        name: str,
        description: str,
        system_type: str,
        user_role: str | None = None,
        llm_settings: LLMSettings | None = None,
    ) -> AISystemAnalysisResult:
        retrieval_query = (
            "Assess AI Act risk level and role-specific obligations for this AI system. "
            f"Name: {name}. Type: {system_type}. Description: {description}."
        )
        retrieval = self.retriever.retrieve(retrieval_query, top_k=5)
        if not retrieval.hits:
            return AISystemAnalysisResult(
                level_of_risk="unclear",
                confidence=0,
                summary=(
                    "No relevant AI Act provisions were retrieved for this system description. "
                    "Refine the description or ingest additional sources before analyzing it."
                ),
                citations=[],
                low_confidence=True,
            )

        active_settings = llm_settings or self.default_llm_settings
        client = LiteLLMClient(active_settings)
        messages = self._build_messages(
            name=name,
            description=description,
            system_type=system_type,
            user_role=user_role,
            hits=retrieval.hits,
            low_confidence=retrieval.low_confidence,
        )
        try:
            raw = client.complete(messages)
            payload = _extract_json_payload(raw)
            risk_level = _normalize_risk_level(payload.get("level_of_risk"))
            model_confidence = _coerce_confidence(payload.get("confidence"))
            retrieval_confidence = int(round(retrieval.confidence * 100))
            combined_confidence = max(0, min(100, int(round((model_confidence + retrieval_confidence) / 2))))
            summary = str(payload.get("summary") or "").strip()
            if not summary:
                raise LLMDependencyError("System analysis did not return a usable summary.")
            if retrieval.low_confidence:
                summary = f"{summary} Retrieval confidence is low, so verify the cited provisions directly."
            return AISystemAnalysisResult(
                level_of_risk=risk_level,
                confidence=combined_confidence,
                summary=summary,
                citations=[build_citation_label(hit, index) for index, hit in enumerate(retrieval.hits, start=1)],
                low_confidence=retrieval.low_confidence,
            )
        except LLMDependencyError:
            logging.getLogger("koala.analysis").info(
                "llm_fallback",
                extra={"event": "analysis.fallback", "reason": "llm_unavailable"},
            )
            return _fallback_analysis(
                name=name,
                description=description,
                system_type=system_type,
                user_role=user_role,
                retrieval=retrieval,
            )

    def _build_messages(
        self,
        *,
        name: str,
        description: str,
        system_type: str,
        user_role: str | None,
        hits: Sequence[RetrievalHit],
        low_confidence: bool,
    ) -> list[dict[str, str]]:
        context = "\n\n".join(build_context_block(hit, index) for index, hit in enumerate(hits, start=1))
        role_note = user_role or "unspecified"
        confidence_note = (
            "Retrieved legal context has low confidence. Be conservative and return 'unclear' if needed."
            if low_confidence
            else "Retrieved legal context is adequate."
        )
        system_prompt = (
            "You assess AI systems under Regulation (EU) 2024/1689.\n"
            "Use only the supplied legal context.\n"
            "Return JSON only, with keys: level_of_risk, confidence, summary.\n"
            "Allowed level_of_risk values: prohibited, high, limited, minimal, general_purpose, unclear.\n"
            "confidence must be an integer from 0 to 100.\n"
            "summary must be 2-4 sentences, mention the user's role when relevant, and cite sources inline like [1]."
        )
        user_prompt = (
            f"User role: {role_note}\n"
            f"System name: {name}\n"
            f"System type: {system_type}\n"
            f"System description: {description}\n"
            f"Instruction: {confidence_note}\n\n"
            "Context:\n"
            f"{context}"
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]


def _extract_json_payload(raw: str) -> dict[str, object]:
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        raise LLMDependencyError("System analysis did not return JSON.")
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise LLMDependencyError("System analysis returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise LLMDependencyError("System analysis JSON must be an object.")
    return payload


def _normalize_risk_level(value: object) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in RISK_LEVELS:
        return RISK_LEVELS[normalized]
    for alias, canonical in RISK_LEVELS.items():
        if alias in normalized:
            return canonical
    return "unclear"


def _coerce_confidence(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        match = re.search(r"\d+(?:\.\d+)?", str(value or ""))
        number = float(match.group(0)) if match else 0.0
    if number <= 1.0:
        number *= 100.0
    return max(0, min(100, int(round(number))))


def _fallback_analysis(
    *,
    name: str,
    description: str,
    system_type: str,
    user_role: str | None,
    retrieval: RetrievalResult,
) -> AISystemAnalysisResult:
    signals, risk_level = _infer_risk_level(name, description, system_type)
    retrieval_confidence = int(round(retrieval.confidence * 100))
    confidence = max(10, min(45, int(round(retrieval_confidence * 0.6))))
    citations = [build_citation_label(hit, index) for index, hit in enumerate(retrieval.hits, start=1)]

    role_note = f"You are reviewing as {user_role}." if user_role else "Role context was not specified."
    if risk_level == "unclear":
        summary = (
            "Sources-only assessment (model generation unavailable). "
            f"{role_note} The description does not match a single AI Act risk tier with high confidence. "
            "Review the cited provisions to determine the applicable obligations."
        )
    else:
        signal_note = f"Signals: {', '.join(signals)}." if signals else ""
        summary = (
            "Sources-only assessment (model generation unavailable). "
            f"{role_note} This system may fall into the {risk_level.replace('_', ' ')} risk tier. "
            f"{signal_note} Review the cited provisions to confirm the exact classification."
        ).strip()

    if retrieval.low_confidence:
        summary = f"{summary} Retrieval confidence is low, so verify the cited provisions directly."

    return AISystemAnalysisResult(
        level_of_risk=risk_level,
        confidence=confidence,
        summary=summary,
        citations=citations,
        low_confidence=retrieval.low_confidence,
    )


def _infer_risk_level(name: str, description: str, system_type: str) -> tuple[list[str], str]:
    text = " ".join([name, system_type, description]).lower()
    signals: list[str] = []

    def has(*tokens: str) -> bool:
        return any(token in text for token in tokens)

    if has("general purpose", "foundation model", "gpai", "llm", "large language"):
        signals.append("general purpose AI")
        return signals, "general_purpose"

    if has("social scoring", "manipulation", "subliminal", "exploit vulnerabilities"):
        signals.append("prohibited practice indicators")
        return signals, "prohibited"

    if has("biometric", "facial recognition", "remote biometric", "emotion recognition"):
        signals.append("biometric or emotion recognition")
        return signals, "high"

    if has("recruitment", "hiring", "employment", "workplace", "education", "credit", "insurance", "healthcare"):
        signals.append("high-impact decision domain")
        return signals, "high"

    if has("chatbot", "virtual assistant", "customer support", "content generation", "deepfake"):
        signals.append("transparency-focused system")
        return signals, "limited"

    if has("recommendation", "personalisation", "analytics"):
        signals.append("general decision support")
        return signals, "minimal"

    return signals, "unclear"
