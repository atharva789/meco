"""
Compatibility shim: import Workflow from the packaged module.
"""

from meco.workflow import Candidate, Workflow

__all__ = ["Workflow", "Candidate"]
