"""Decide whether an E-Rate RFP is one Mission Telecom can actually bid on
and win, using its real capability profile (config.MISSION_TELECOM).

Mission Telecom is a nonprofit wireless ISP on the T-Mobile network. The RFPs
it should chase are E-Rate Category 1 internet access / data transmission at
bandwidths a wireless carrier can serve — especially for libraries (hotspot
lending) and schools. The RFPs it should NOT chase are dedicated fiber builds,
multi-gigabit circuits, and Category 2 internal-connections hardware (switches,
routers, firewalls, access points, cabling, UPS).

assess() returns a structured verdict that scoring.py turns into points and
that the dashboard uses to filter to biddable opportunities.
"""
import json
import re

from . import config


# A number immediately followed by a bandwidth unit token. The negative
# lookahead keeps the bare "g"/"m"/"t" units from matching inside ordinary
# words ("Gateway", "Managed", "Technology") — that false-match was turning
# the funding year 2027 into multi-terabit "requirements".
_BW_RE = re.compile(
    r"([\d,.]+)\s*(gbps|mbps|tbps|gbit|mbit|kbps|gig|gb|mb|kb|g|m|t|k)(?![a-z])")


def _mbps(text: str | None) -> float:
    """Parse a bandwidth figure (in Mbps) from a structured capacity string:
    '1 Gbps', '1024.00 Mbps', '10G'. Returns 0 when no clean figure."""
    if not text:
        return 0.0
    best = 0.0
    for m in _BW_RE.finditer(str(text).lower()):
        try:
            val = float(m.group(1).replace(",", "").rstrip("."))
        except ValueError:
            continue
        unit = m.group(2)
        if unit.startswith("t"):
            val *= 1_000_000
        elif unit.startswith("g"):
            val *= 1000
        elif unit.startswith("k"):
            val /= 1000
        best = max(best, val)
    return best


def assess(row: dict, service_requests: list[dict]) -> dict:
    """row: an rfps table row (dict). service_requests: its line items.

    Returns:
      biddable       -> can Mission Telecom deliver/win this?
      service_fraction (0-1) -> for the service-match scoring bucket
      matched        -> Mission catalog terms found
      wireless_signal-> RFP explicitly wants wireless/cellular (strong fit)
      max_mbps       -> largest bandwidth requested
      blockers       -> plain-English reasons it's a poor/no fit
    """
    prof = config.MISSION_TELECOM
    service_types = _list(row, "service_types")
    functions = _list(row, "functions")
    st_lower = [s.lower() for s in service_types]
    fn_lower = [f.lower() for f in functions]

    # text blob for term matching
    parts = list(service_types) + list(functions)
    for f in ("cat1_description", "cat2_description"):
        if row.get(f):
            parts.append(str(row[f]))
    for sr in service_requests:
        for k in ("service_type", "function", "manufacturer"):
            if sr.get(k):
                parts.append(str(sr[k]))
    blob = " ; ".join(parts).lower()

    # largest requested bandwidth — ONLY from the structured capacity fields,
    # which are clean ("1024.00 Mbps"). Free-text descriptions are too noisy
    # (years, phone numbers, quantities) to parse bandwidth from reliably.
    max_mbps = 0.0
    for sr in service_requests:
        for k in ("max_capacity", "min_capacity"):
            max_mbps = max(max_mbps, _mbps(sr.get(k)))

    # highest MIN capacity across line items = the real bandwidth floor the
    # applicant needs (more meaningful than MAX, which applicants routinely
    # inflate in the E-Rate portal).
    min_need = 0.0
    for sr in service_requests:
        min_need = max(min_need, _mbps(sr.get("min_capacity")))

    # Biddability is decided by the STRUCTURED function field, which reliably
    # separates a plain internet-access buy (wireless-serviceable) from a
    # fiber/infrastructure build. Bandwidth is NOT a disqualifier — the
    # portal's min/max capacity values are too often junk (a small school
    # listing a 76 Gbps "minimum") to hard-gate on.
    serviceable_funcs = ("internet access and data transmission service",
                         "standalone internet access service",
                         "standalone data transmission service")
    has_serviceable = any(any(s in fn for s in serviceable_funcs)
                          for fn in fn_lower)
    has_fiber = any("fiber" in fn for fn in fn_lower)
    only_excluded = bool(st_lower) and all(
        st in prof["excluded_service_types"] for st in st_lower)

    matched = sorted({t for t in prof["core_terms"] if t in blob})
    # A wireless-WAN signal means the applicant wants connectivity delivered
    # wirelessly — Mission Telecom's exact product. Match only unambiguous
    # terms; bare "wireless" is excluded because E-Rate's Category 2
    # "Wireless Access Points / Controllers" are building-Wi-Fi LAN hardware,
    # not wireless WAN.
    wireless_signal = any(t in blob for t in
                          ("cellular", "lte", "5g", "4g", "fixed wireless",
                           "hotspot", "mobile broadband", "mobile data"))

    biddable = has_serviceable and not has_fiber

    blockers = []
    if has_fiber:
        blockers.append(
            "requires leased fiber — beyond Mission Telecom's wireless "
            "delivery on the T-Mobile network")
    if not has_serviceable:
        if only_excluded:
            blockers.append(
                "Category 2 internal-connections hardware only (switches, "
                "routers, firewalls, access points, cabling) — Mission "
                "Telecom provides connectivity, not LAN equipment")
        else:
            blockers.append(
                "no wireless-serviceable internet-access / data-transmission "
                "line item")

    concerns = []
    if biddable and min_need >= 2000:  # 2 Gbps floor
        concerns.append(
            f"high stated bandwidth floor ({_fmt_bw(min_need)}) — confirm "
            "fixed wireless / cellular can serve it")

    # service-match fraction (0-1) for the scoring bucket
    if not biddable:
        frac = 0.1
    else:
        frac = 0.6  # a serviceable Category 1 internet/data RFP
        if wireless_signal:
            frac += 0.25  # RFP explicitly wants wireless — Mission's product
        if max_mbps and max_mbps <= prof["sweet_spot_mbps"]:
            frac += 0.1  # modest bandwidth is the wireless sweet spot
        if min_need >= 2000:
            frac -= 0.15  # high floor — less certain wireless can serve
        if "librar" in (row.get("applicant_type") or "").lower() \
                and ("hotspot" in blob or "lending" in blob):
            frac += 0.1  # library hotspot-lending = Project: Volume Up
        frac = max(0.1, min(frac, 1.0))

    return {
        "biddable": biddable,
        "service_fraction": round(frac, 3),
        "matched": matched,
        "wireless_signal": wireless_signal,
        "max_mbps": max_mbps,
        "min_need_mbps": min_need,
        "blockers": blockers,
        "concerns": concerns,
    }


def _list(row: dict, field: str) -> list:
    try:
        return json.loads(row.get(field) or "[]")
    except (TypeError, json.JSONDecodeError):
        return []


def _fmt_bw(mbps: float) -> str:
    if mbps >= 1000:
        g = mbps / 1000
        return f"{g:.0f} Gbps" if g == int(g) else f"{g:.1f} Gbps"
    return f"{mbps:.0f} Mbps"
