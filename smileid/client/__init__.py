"""Hand-written client layer: configuration, transport, auth (spec §2, §3).

This tree owns everything a code generator must not touch: the HTTP transport,
the JWT lifecycle and the HMAC signing hook.
"""

from smileid.client.client import Client
from smileid.client.config import ClientConfig, Environment

__all__ = ["Client", "ClientConfig", "Environment"]
