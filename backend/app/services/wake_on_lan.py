import re
import socket


MAC_PATTERN = re.compile(r"^[0-9A-Fa-f]{12}$")


def normalize_mac(mac_address: str) -> str:
    cleaned = re.sub(
        r"[^0-9A-Fa-f]",
        "",
        mac_address or ""
    )

    if not MAC_PATTERN.fullmatch(cleaned):
        raise ValueError("Adresse MAC invalide")

    return cleaned.upper()


def build_magic_packet(mac_address: str) -> bytes:
    normalized = normalize_mac(mac_address)
    mac_bytes = bytes.fromhex(normalized)

    return b"\xff" * 6 + mac_bytes * 16


def send_magic_packet(
    mac_address: str,
    broadcast_address: str = "255.255.255.255",
    port: int = 9,
) -> None:
    packet = build_magic_packet(mac_address)

    with socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM
    ) as sock:
        sock.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_BROADCAST,
            1
        )

        sock.settimeout(5)

        sock.sendto(
            packet,
            (
                broadcast_address,
                int(port)
            )
        )
