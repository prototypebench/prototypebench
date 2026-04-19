"""PrototypeBench evaluation harness.

Phase 2 goal: automated extraction of FAIL_TO_PASS / PASS_TO_PASS sets and
scoring of agent patches against them. The extractor and the scorer share the
same execution core — the only difference is whether `agent_patch` or
`head_commit` provides the candidate solution.
"""

__version__ = "0.0.1"
