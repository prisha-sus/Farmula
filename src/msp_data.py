# -*- coding: utf-8 -*-
"""
MSP (Minimum Support Price) reference data for supported commodities.
Source: Cabinet approvals, Government of India.
Onion and potato have no MSP — covered by Price Stabilisation Fund instead.
"""

MSP_DATA = {
    "soyabean": {
        "msp": 5328,
        "season": "Kharif 2025-26",
        "has_msp": True,
        "note": "Government MSP — NAFED procurement available"
    },
    "potato": {
        "msp": None,
        "season": None,
        "has_msp": False,
        "note": "No MSP — covered under Price Stabilisation Fund (PSF)"
    },
    "onion": {
        "msp": None,
        "season": None,
        "has_msp": False,
        "note": "No MSP — covered under Price Stabilisation Fund (PSF)"
    },
}


def get_msp_info(commodity: str) -> dict:
    """Returns MSP info for a commodity. Case-insensitive."""
    return MSP_DATA.get(commodity.lower(), {
        "has_msp": False,
        "note": "MSP data not available for this commodity"
    })


def get_msp_status(commodity: str, current_price: float) -> dict:
    """
    Returns MSP comparison status for display in UI.
    Returns dict with: has_msp, msp, status, delta, color, message
    """
    info = get_msp_info(commodity)

    if not info["has_msp"]:
        return {
            "has_msp": False,
            "message": info["note"],
            "color": "gray"
        }

    msp = info["msp"]
    delta = current_price - msp
    pct = (delta / msp) * 100

    if delta >= 0:
        status = "above"
        color = "green"
        message = f"Rs.{delta:,.0f}/q above MSP ({pct:+.1f}%) — good time to sell"
    else:
        status = "below"
        color = "red"
        message = f"Rs.{abs(delta):,.0f}/q below MSP ({pct:.1f}%) — consider PSF procurement"

    return {
        "has_msp": True,
        "msp": msp,
        "season": info["season"],
        "delta": delta,
        "status": status,
        "color": color,
        "message": message,
        "pct": pct
    }
