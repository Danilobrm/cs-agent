"""Bootstrap: wire the store, policy, tool context and LLM into an Agent."""

from datetime import time

from cs_agent.agent import Agent
from cs_agent.config import Settings
from cs_agent.data import load_policy, load_store
from cs_agent.llm import create_llm
from cs_agent.tools.context import ToolContext


def build_agent(settings: Settings, fixed_time: time | None = None) -> Agent:
    """Build the agent for `settings`. Raises ConfigError when the LLM cannot be configured.

    `fixed_time` pins the clock time of day (reproducible transcripts and evals).
    """
    llm = create_llm(settings)
    store = load_store(settings.data_dir)
    policy = load_policy(settings.data_dir)
    ctx = ToolContext.create(store, settings.reference_date, fixed_time=fixed_time)
    return Agent(llm, ctx, policy)
