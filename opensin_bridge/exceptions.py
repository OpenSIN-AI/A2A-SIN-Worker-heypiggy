"""Compatibility exceptions for the bridge contract layer.

The package still exposes the legacy :class:`BridgeError` and
:class:`ContractMismatch` from :mod:`opensin_bridge.contract`, but this module
gives newer code a narrower place to import retry-classified errors from.
"""

from __future__ import annotations

from opensin_bridge.contract import BridgeError, ContractMismatch


class TransientError(BridgeError):
    """Bridge error that may be retried."""


class PermanentError(BridgeError):
    """Bridge error that must not be retried."""


__all__ = ["BridgeError", "ContractMismatch", "TransientError", "PermanentError"]
