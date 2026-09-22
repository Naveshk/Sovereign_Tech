from dataclasses import asdict, dataclass


@dataclass
class NetworkPolicy:
    sandbox_network: str = "disabled"
    cloud_calls_allowed: bool = False
    external_outbound_allowed: bool = False
    local_services_allowed: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


NETWORK_POLICY = NetworkPolicy()
