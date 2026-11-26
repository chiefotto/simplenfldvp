import math

WEIGHT = 0.50
MIN_MULTIPLIER = 0.50
MAX_MULTIPLIER = 1.50
Z_ALPHA = 0.15


def _finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _cap(raw):
    if raw > MAX_MULTIPLIER:
        return MAX_MULTIPLIER, True
    if raw < MIN_MULTIPLIER:
        return MIN_MULTIPLIER, True
    return raw, False


def _unavailable(reason):
    return {
        "player_avg": None,
        "adjusted": None,
        "multiplier": None,
        "adjustment_pct": None,
        "method": None,
        "capped": False,
        "baseline_only": True,
        "reason": reason,
    }


def _baseline_only(baseline, reason):
    result = _unavailable(reason)
    result["player_avg"] = baseline
    return result


def _adjusted(baseline, multiplier, capped, method, reason=None):
    return {
        "player_avg": baseline,
        "adjusted": baseline * multiplier,
        "multiplier": multiplier,
        "adjustment_pct": (multiplier - 1) * 100,
        "method": method,
        "capped": capped,
        "baseline_only": False,
        "reason": reason,
    }


def estimate_ratio(player_avg, defense_avg, league_avg, weight=WEIGHT):
    """Shrink the defense-to-league allowance toward the player's own average.

    This does not change the defensive z-score. A zero average stays zero.
    """
    baseline = _finite(player_avg)
    if baseline is None:
        return _unavailable("Not enough data.")
    if baseline < 0:
        return _baseline_only(baseline, "A negative baseline is shown without a matchup multiplier.")
    defense = _finite(defense_avg)
    league = _finite(league_avg)
    if defense is None or defense < 0 or league is None or league <= 0:
        return _baseline_only(baseline, "The matchup factor is unavailable, so the baseline is unchanged.")
    raw = 1 + weight * ((defense / league) - 1)
    multiplier, capped = _cap(raw)
    reason = "A cap limited the matchup factor." if capped else None
    if baseline == 0:
        reason = "A zero baseline stays zero."
    return _adjusted(baseline, multiplier, capped, "ratio", reason)


def estimate_z(player_avg, z_score, alpha=Z_ALPHA):
    """Alternate comparison adjustment. It is not the production default."""
    baseline = _finite(player_avg)
    if baseline is None:
        return _unavailable("Not enough data.")
    if baseline < 0:
        return _baseline_only(baseline, "A negative baseline is shown without a matchup multiplier.")
    score = _finite(z_score)
    if score is None:
        return _baseline_only(baseline, "The z-score adjustment is unavailable.")
    multiplier, capped = _cap(1 + alpha * score)
    reason = "A cap limited the matchup factor." if capped else None
    if baseline == 0:
        reason = "A zero baseline stays zero."
    return _adjusted(baseline, multiplier, capped, "z", reason)
