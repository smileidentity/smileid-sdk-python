"""Hand-written client layer: configuration, transport, auth.

This tree owns everything a code generator must not touch: the HTTP transport
and the JWT lifecycle.
"""

from usesmileid.client.client import Client
from usesmileid.client.config import ClientConfig, Environment

__all__ = ["Client", "ClientConfig", "Environment"]
