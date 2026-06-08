"""CV-driven job-search agent."""
from .agent import JobAgent, save_reports, AgentResult
from .profile import CandidateProfile, Job

__all__ = ["JobAgent", "save_reports", "AgentResult", "CandidateProfile", "Job"]
__version__ = "0.1.0"
