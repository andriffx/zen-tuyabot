"""The diagnostic must name the real cause, not just "failed"."""

from __future__ import annotations

import socket

from tuyabot.devices import diagnostics


def test_a_device_without_an_ip_is_reported_before_any_network_call(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("no network probe should run without an IP")

    monkeypatch.setattr(diagnostics, "_tcp_probe", explode)

    report = diagnostics.diagnose({"name": "kosong", "ip": "", "local_key": "k"})

    assert report["checks"] == []
    assert any("belum punya IP" in hint for hint in report["hints"])


def test_a_refused_port_points_at_the_key_not_the_network(monkeypatch):
    monkeypatch.setattr(
        diagnostics, "_tcp_probe", lambda host, port, timeout: {"ok": True, "detail": "port terbuka"}
    )
    monkeypatch.setattr(diagnostics, "_local_addresses", lambda: ["192.168.1.10"])

    report = diagnostics.diagnose(
        {"name": "pompa", "ip": "192.168.1.50", "version": 3.5, "local_key": "k"}
    )

    assert report["checks"][0]["ok"] is True
    assert any("local key" in hint for hint in report["hints"])


def test_a_timeout_on_another_subnet_explains_the_bridge_network(monkeypatch):
    monkeypatch.setattr(
        diagnostics,
        "_tcp_probe",
        lambda host, port, timeout: {"ok": False, "detail": "timeout 3s"},
    )
    monkeypatch.setattr(diagnostics, "_local_addresses", lambda: ["172.21.0.2"])

    report = diagnostics.diagnose(
        {"name": "pompa", "ip": "192.168.1.50", "version": 3.5, "local_key": "k"}
    )

    combined = " ".join(report["hints"])
    assert "subnet berbeda" in combined
    assert "network_mode: host" in combined


def test_a_missing_key_is_called_out_even_when_the_port_answers(monkeypatch):
    monkeypatch.setattr(
        diagnostics, "_tcp_probe", lambda host, port, timeout: {"ok": True, "detail": "port terbuka"}
    )

    report = diagnostics.diagnose({"name": "pompa", "ip": "192.168.1.50", "version": 3.5})

    assert report["device"]["has_local_key"] is False
    assert any("Local key kosong" in hint for hint in report["hints"])


def test_the_local_key_value_is_never_included(monkeypatch):
    monkeypatch.setattr(
        diagnostics, "_tcp_probe", lambda host, port, timeout: {"ok": True, "detail": "port terbuka"}
    )
    secret = "super-secret-local-key"

    report = diagnostics.diagnose(
        {"name": "pompa", "ip": "192.168.1.50", "version": 3.5, "local_key": secret}
    )

    assert secret not in str(report)
    assert report["device"]["has_local_key"] is True


def test_tcp_probe_reports_a_closed_port_without_raising():
    # Bind then close: the port is free, so the connect is refused.
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    result = diagnostics._tcp_probe("127.0.0.1", port, 1.0)

    assert result["ok"] is False
    assert "refused" in result["detail"] or "timeout" in result["detail"]
