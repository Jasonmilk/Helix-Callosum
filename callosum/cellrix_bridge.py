"""Cellrix Bridge for Helix-Callosum.

Implements CIS v0.3.0 — zero dependency on Cellrix. Returns a plain dict.

Usage:
    cellrix check          # Validates this bridge's output
    cellrix preview .      # Renders the dashboard from this bridge
"""


def build_manifest(config: dict | None = None) -> dict:
    """Return a Cellrix Manifest v2.0 dict for the Callosum dashboard.

    Currently provides a static snapshot because Cellrix does not yet
    support 'http' as a source type for dynamic cells.
    """
    manifest = {
        "version": "2.0",
        "layout": {
            "direction": "horizontal",
            "slots": [
                {"id": "status", "weight": 1},
                {"id": "live", "weight": 2},
            ],
        },
        "cells": [
            {
                "id": "callosum_header",
                "type": "static",
                "slot": "status",
                "content": (
                    " HELIX-CALLOSUM v0.1.0\n"
                    " Context Memory Allocator\n"
                    " ─────────────────────────\n"
                    " Health: ● ONLINE\n"
                    " Backend: Tuck/Local\n"
                    " Min Savings Thr: 200 tok\n"
                    " Eviction Policy: hybrid\n"
                ),
                "priority": 100,
            },
            {
                "id": "event_log",
                "type": "static",
                "slot": "live",
                "content": (
                    " Live Request Log\n"
                    " ─────────────────\n"
                    " Waiting for incoming requests...\n"
                    " Run: curl -X POST .../v1/compile\n"
                ),
                "priority": 100,
            },
        ],
    }
    return manifest
