"""DNS fallback resolution utility for VIYON Billing System.

Resolves external database hostnames (such as Neon PostgreSQL) using trusted public DNS resolvers
(Google DNS: 8.8.8.8, Cloudflare DNS: 1.1.1.1) when local ISP or router DNS servers fail or refuse queries.
"""

import logging
import socket
from typing import Any, List, Tuple

logger = logging.getLogger("viyon_billing")

_orig_getaddrinfo = socket.getaddrinfo

# Trusted public DNS servers for fallback resolution
FALLBACK_DNS_SERVERS = ["8.8.8.8", "1.1.1.1", "8.8.4.4"]

_installed = False


def _is_ip_address(host: str) -> bool:
    """Check if the string is already an IPv4 or IPv6 address."""
    if not host or not isinstance(host, str):
        return False
    try:
        socket.inet_aton(host)
        return True
    except (socket.error, ValueError):
        pass
    try:
        socket.inet_pton(socket.AF_INET6, host)
        return True
    except (socket.error, ValueError, AttributeError):
        pass
    return False


def patched_getaddrinfo(
    host: Any,
    port: Any,
    family: int = 0,
    type: int = 0,
    proto: int = 0,
    flags: int = 0,
) -> List[Tuple[Any, ...]]:
    """Resolve hostname using system resolver, falling back to public DNS on gaierror."""
    try:
        return _orig_getaddrinfo(host, port, family, type, proto, flags)
    except socket.gaierror as gai_err:
        if isinstance(host, str) and not _is_ip_address(host):
            try:
                import dns.resolver

                resolver = dns.resolver.Resolver(configure=False)
                resolver.nameservers = FALLBACK_DNS_SERVERS
                resolver.timeout = 2.5
                resolver.lifetime = 4.0

                # Resolve A records (IPv4)
                answers = resolver.resolve(host, "A")
                results: List[Tuple[Any, ...]] = []
                for rdata in answers:
                    try:
                        resolved_entries = _orig_getaddrinfo(
                            rdata.address, port, family, type, proto, flags
                        )
                        results.extend(resolved_entries)
                    except Exception:
                        continue

                if results:
                    return results
            except Exception as fallback_exc:
                logger.debug(
                    "Public DNS fallback failed for '%s': %s", host, fallback_exc
                )

        raise gai_err


def install_dns_fallback() -> None:
    """Install the socket.getaddrinfo patch idempotently."""
    global _installed
    if not _installed:
        socket.getaddrinfo = patched_getaddrinfo
        _installed = True
        logger.info("DNS fallback resolver successfully installed.")


# Auto-install on module import
install_dns_fallback()
