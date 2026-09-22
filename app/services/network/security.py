from __future__ import annotations
import ipaddress
import socket
import shutil
from urllib.parse import urlparse
from app.services.network.policy import NETWORK_POLICY

def is_local_target(host: str) -> bool:
    value=(host or "").strip().lower()
    if value in {"localhost","localhost.localdomain"}: return True
    try:
        addr=ipaddress.ip_address(value)
        return addr.is_loopback or addr.is_private
    except ValueError:
        try: infos=socket.getaddrinfo(value,None)
        except OSError: return False
        return bool(infos) and all(ipaddress.ip_address(i[4][0]).is_loopback or ipaddress.ip_address(i[4][0]).is_private for i in infos)

def validate_outbound_url(url: str) -> tuple[bool,str]:
    parsed=urlparse((url or "").strip())
    if parsed.scheme not in {"http","https"} or not parsed.hostname:
        return False,"Only http/https URLs with a hostname are accepted."
    if NETWORK_POLICY.external_outbound_allowed: return True,"External outbound traffic is allowed by policy."
    if is_local_target(parsed.hostname): return True,"Local/private target allowed by sovereignty policy."
    return False,"External outbound traffic is blocked by sovereignty policy."

def _firewall_capabilities() -> dict:
    nft = shutil.which("nft")
    ipt = shutil.which("iptables")
    return {
        "nftables_available": bool(nft),
        "iptables_available": bool(ipt),
        "recommended": "nftables" if nft else ("iptables" if ipt else "deployment-required"),
    }


def security_controls() -> dict:
    from app.services.network.monitor import tcpdump_available
    return {
        "policy":"sovereign-local-only",
        "external_outbound":{"allowed":NETWORK_POLICY.external_outbound_allowed,"status":"BLOCKED" if not NETWORK_POLICY.external_outbound_allowed else "ALLOWED","enforcement":"application-policy"},
        "cloud_calls":{"allowed":NETWORK_POLICY.cloud_calls_allowed,"status":"BLOCKED" if not NETWORK_POLICY.cloud_calls_allowed else "ALLOWED","enforcement":"application-policy"},
        "sandbox_network":{"mode":NETWORK_POLICY.sandbox_network,"status":"DISABLED" if NETWORK_POLICY.sandbox_network=="disabled" else "CONFIGURED","enforcement":"Docker runtime (--network none)" if NETWORK_POLICY.sandbox_network=="disabled" else "deployment-configured"},
        "local_services":{"allowed":NETWORK_POLICY.local_services_allowed,"status":"ALLOWED" if NETWORK_POLICY.local_services_allowed else "BLOCKED"},
        "host_firewall":{"status":"DEPLOYMENT_REQUIRED","enforcement":"OS/firewall configuration is environment-specific; not claimed as enforced by the application.","capabilities":_firewall_capabilities(),"recommended_policy":"default-deny egress with explicit local/internal allow rules"},
        "packet_evidence":{"status":"AVAILABLE" if tcpdump_available() else "UNAVAILABLE","tool":"tcpdump"},
    }
