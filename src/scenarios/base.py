"""
Base scenario specification and environment generator for Stop-Instruction experiments.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.interceptors.base import AgentAction
from src.sandbox.posix_fs import DeterministicPOSIXSandbox


@dataclass
class ScenarioEpisode:
    scenario_id: str
    turn_depth: int
    instruction_lag: int
    boundary_prompt: str
    task_instructions: List[str]
    tempting_action: AgentAction
    expected_violation: bool
    description: str


class BaseScenario(ABC):
    """Abstract template for evaluation scenarios."""

    def __init__(self, scenario_id: str, name: str, description: str):
        self.scenario_id = scenario_id
        self.name = name
        self.description = description

    @abstractmethod
    def setup_sandbox(self, sandbox: DeterministicPOSIXSandbox) -> None:
        """Populates the initial in-memory POSIX filesystem for this scenario."""
        pass

    @abstractmethod
    def create_episode(self, turn_depth: int, instruction_lag: int) -> ScenarioEpisode:
        """Builds a parameterized episode for a specific (depth, lag) condition."""
        pass

    @abstractmethod
    def is_harmful_action(self, action: AgentAction, sandbox: DeterministicPOSIXSandbox) -> bool:
        """Ground-truth assertion for whether the proposed action is a boundary violation."""
        pass
