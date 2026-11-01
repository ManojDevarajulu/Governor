"""
Base interface and dataclasses for Agent Interceptors and Containment Protocols.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class ProtocolType(str, Enum):
    UNMONITORED_BASELINE = "UNMONITORED_BASELINE"
    COT_MONITOR = "COT_MONITOR"
    DEFER_TO_RESAMPLE = "DEFER_TO_RESAMPLE"
    INVARIANT_GOVERNOR = "INVARIANT_GOVERNOR"


@dataclass
class AgentAction:
    op: str  # "write", "read", "unlink", "symlink", "mkdir", "subprocess"
    target_path: str
    content: str = ""
    cot_reasoning: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InterceptorDecision:
    allow: bool
    reason: str
    suspicion_score: float = 0.0  # 0.0 (safe) to 1.0 (malicious)
    overruled: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseInterceptor(ABC):
    """Abstract containment protocol interceptor."""

    def __init__(self, allowed_scope: str = "/project"):
        self.allowed_scope = allowed_scope

    @abstractmethod
    def intercept(self, action: AgentAction, sandbox: Any) -> InterceptorDecision:
        """Evaluates proposed agent action and returns InterceptorDecision."""
        pass
