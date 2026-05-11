"""Cellrix Bridge for Helix-Callosum.

Implements CIS v0.3.0 — zero dependency on Cellrix. Returns a plain dict.

Usage:
    cellrix check          # Validates this bridge's output
    cellrix preview .      # Renders the dashboard from this bridge
"""


def build_manifest(config: dict | None = None) -> dict:
    """Return a Cellrix Manifest v2.0 dict for the Callosum dashboard.

    Layout:
        ┌────────────────────────────────────────────┐
        │  HELIX-CALLOSUM v0.1.0       ? for help     │
        ├──────────────────────┬──────────────────────┤
        │  Core Status          │  Live Request Log    │
        │  Health: ● ONLINE     │  [dynamic] scrolling │
        │  Backend: anthropic   │                      │
        │  Threshold: 200       │                      │
        │  Cache Hit Rate: 0.0% │                      │
        ├──────────────────────┴──────────────────────┤
        │  F1 Help  Tab Focus  q Quit                 │
        └────────────────────────────────────────────┘
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
            # Sidebar — realtime status (polled every 2s)
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
                "id": "callosum_stats",
                "type": "dynamic",
                "slot": "status",
                "source": {
                    "type": "http",
                    "url": "http://localhost:8687/v1/usage-stats",
                    "refresh_interval_ms": 2000,
                },
                "content_type": "json",
                "collapseMode": "scroll",
                "priority": 50,
            },
            # Main panel — live event log (dynamic)
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
