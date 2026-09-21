"""Error types shared by the CLI layers."""

from __future__ import annotations


class UsageError(Exception):
    """Bad invocation or bad configuration: exit code 2, nothing is submitted."""


class WorkflowError(Exception):
    """The workflow JSON cannot be loaded, or its target node cannot be resolved."""


class MappingError(UsageError):
    """A CLI value cannot be mapped onto one of the node's enums."""


class ComfyError(Exception):
    """The ComfyUI server answered with an error."""


class ServerError(Exception):
    """The ComfyUI server could not be started, reached or kept alive."""
