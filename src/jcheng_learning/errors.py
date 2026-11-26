"""Typed errors and stable exit codes for the dataset CLI."""

from __future__ import annotations


class JchengError(Exception):
    """Base class for expected, user-facing failures."""

    exit_code = 1


class DatasetError(JchengError):
    """A dataset is malformed, inconsistent or fails a check."""

    exit_code = 1


class UsageError(JchengError):
    """The command line or a required argument is invalid."""

    exit_code = 2


class DependencyError(JchengError):
    """An optional dependency (for example ``lerobot`` or ``av``) is missing."""

    exit_code = 3


class InconclusiveError(JchengError):
    """The input cannot be judged with the available information.

    Inconclusive is never treated as a pass.
    """

    exit_code = 4
