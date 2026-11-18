"""Reachability diagnostics for a device.

Answers "can this process reach the device at all?" separately from "did the
Tuya handshake succeed?". Without that split, an unreachable device and a wrong
local key both surface as the same "tidak membalas", which is undiagnosable from
a container that may simply not be on the device's network.
"""

from __future__ import annotations

import socket
from typing import Any


def _local_addresses() -> list[str]:
    """Addresses of this host, which reveal whether it is even on the LAN."""
    found: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            found.add(info[4][0])
    except OSError:
        pass
    # The address used for outbound traffic; UDP connect sends no packet.
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("10.255.255.255", 1))
            found.add(probe.getsockname()[0])
        finally:
            probe.close()
    except OSError:
        pass
    return sorted(found)


def _tcp_probe(host: str, port: int, timeout: float) -> dict[str, Any]:
    """The Tuya protocol listens on TCP 6668; a refused/timed-out connect
    separates a routing problem from an application problem."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        return {"ok": True, "detail": "port terbuka"}
    except TimeoutError:
        return {"ok": False, "detail": f"timeout {timeout:.0f}s (paket tidak sampai / diblokir)"}
    except ConnectionRefusedError:
        return {"ok": False, "detail": "connection refused (IP hidup, port tertutup)"}
    except OSError as exc:
        return {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}
    finally:
        sock.close()


def _same_subnet(a: str, b: str) -> bool | None:
    """Compare the first three octets: enough to say "likely same LAN"."""
    try:
        return a.split(".")[:3] == b.split(".")[:3]
    except AttributeError:
        return None


def diagnose(device: dict[str, Any], *, timeout: float = 3.0) -> dict[str, Any]:
    host = (device.get("ip") or "").strip()
    addresses = _local_addresses()
    report: dict[str, Any] = {
        "device": {
            "name": device.get("name"),
            "ip": host or None,
            "tuya_id": device.get("tuya_id"),
            "version": device.get("version"),
            "has_local_key": bool(device.get("local_key")),
        },
        "container": {"addresses": addresses},
        "checks": [],
        "hints": [],
    }

    if not host:
        report["hints"].append(
            "Perangkat belum punya IP. Isi IP-nya (atau pakai scan bila container satu LAN)."
        )
        return report

    tcp = _tcp_probe(host, 6668, timeout)
    report["checks"].append({"name": "tcp-6668", "target": f"{host}:6668", **tcp})

    if not device.get("local_key"):
        report["hints"].append("Local key kosong: handshake Tuya pasti gagal.")
    if str(device.get("version") or "") not in {"3.1", "3.3", "3.4", "3.5"}:
        report["hints"].append(
            f"Versi protokol '{device.get('version')}' tidak lazim; coba 3.3 atau 3.5."
        )

    if tcp["ok"]:
        report["hints"].append(
            "Port 6668 terbuka: jaringan OK. Kalau kontrol tetap gagal, tersangka utama "
            "adalah local key atau versi protokol."
        )
        return report

    # Reachability failed. Say why, in terms the operator can act on.
    report["hints"].append(
        "Container tidak bisa menjangkau port 6668. Perangkat Tuya hanya bisa dikontrol "
        "dari jaringan yang sama (LAN), bukan lewat internet."
    )
    if addresses:
        same = _same_subnet(addresses[0], host)
        if same is False:
            report["hints"].append(
                f"Alamat container ({addresses[0]}) dan perangkat ({host}) berada di subnet "
                "berbeda. Ini penyebab paling mungkin: container memakai bridge network, "
                "jadi paket ke LAN rumah tidak pernah keluar."
            )
    report["hints"].append(
        "Opsi: jalankan container dengan network_mode: host di host yang satu LAN, "
        "atau hubungkan server ke LAN lewat tunnel (WireGuard/Tailscale)."
    )
    return report
