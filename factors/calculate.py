"""Daily crowding factor reference calculations, using point-in-time inputs."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from math import ceil, isfinite
from statistics import fmean, median


@dataclass(frozen=True)
class StockDay:
    symbol: str
    industry: str | None
    amount: float | None
    lag_float_cap: float | None
    return_: float | None
    cap_eligible: bool = True


def _validate(rows):
    symbols = {row.symbol for row in rows}
    if len(symbols) != len(rows) or "" in symbols:
        raise ValueError("symbols must be unique and nonempty on each trading day")
    for r in rows:
        for x in (r.amount, r.lag_float_cap, r.return_):
            if x is not None and not isfinite(x):
                raise ValueError(f"nonfinite input for {r.symbol}")
        if r.amount is not None and r.amount < 0:
            raise ValueError(f"negative turnover for {r.symbol}")
        if r.lag_float_cap is not None and r.lag_float_cap <= 0:
            raise ValueError(f"nonpositive float market cap for {r.symbol}")
        if r.return_ is not None and r.return_ < -1:
            raise ValueError(f"return below -100% for {r.symbol}")


def _coverage(observed, expected):
    return observed / expected if expected else None


def _meets(ratio, minimum):
    return ratio is not None and ratio >= minimum


def _amount(rows):
    return sum(r.amount for r in rows if r.amount is not None)


def _cap(rows):
    return sum(r.lag_float_cap for r in rows if r.lag_float_cap is not None)


def _amount_coverage(rows):
    return _coverage(sum(r.amount is not None for r in rows), len(rows))


def _cap_sample(rows):
    eligible = [r for r in rows if r.cap_eligible]
    joint = [r for r in eligible if r.amount is not None and r.lag_float_cap is not None]
    return joint, _coverage(len(joint), len(eligible)), _coverage(_amount(joint), _amount(rows))


def freeze_head(month_open_symbols, history):
    """history maps symbol to 20 calendar-aligned amounts ending the prior month."""
    symbols = set(month_open_symbols)
    ranking = []
    for symbol in sorted(symbols):
        values = history.get(symbol)
        if values is None:
            continue
        if len(values) != 20:
            raise ValueError(f"need 20 prior sessions for {symbol}")
        active = [x for x in values if x is not None]
        if any(not isfinite(x) or x < 0 for x in active):
            raise ValueError(f"invalid historical turnover for {symbol}")
        if len(active) >= 16:
            ranking.append((median(active), symbol))
    if len(ranking) < 2 or not _meets(_coverage(len(ranking), len(symbols)), .95):
        return None
    ranking.sort(key=lambda pair: (-pair[0], pair[1]))
    count = min(ceil(len(ranking) * .20), len(ranking) - 1)
    return frozenset(symbol for _, symbol in ranking[:count])


def daily_factors(market, industry, head=None):
    """market contains one row per expected stock. None means unavailable."""
    rows = list(market)
    _validate(rows)
    segment = [r for r in rows if r.industry == industry]
    known = _amount(segment)
    overall = _amount(rows)
    amount_industry = _amount_coverage(segment)
    amount_market = _amount_coverage(rows)
    amounts_ok = _meets(amount_industry, .95) and _meets(amount_market, .95)

    joint_u, cap_num_u, cap_amt_u = _cap_sample(segment)
    joint_m, cap_num_m, cap_amt_m = _cap_sample(rows)
    caps_ok = amounts_ok and all(
        _meets(x, .95) for x in (cap_num_u, cap_amt_u, cap_num_m, cap_amt_m)
    )
    amount_u, amount_m = _amount(joint_u), _amount(joint_m)
    cap_u, cap_m = _cap(joint_u), _cap(joint_m)
    direction = [r for r in segment if r.amount and r.return_ is not None]
    direction_amount = _amount(direction)
    direction_cov = _coverage(direction_amount, known)
    active = [r.amount for r in segment if r.amount and r.amount > 0]
    result = {
        "S": known / overall if amounts_ok and overall > 0 else None,
        "S_joint": amount_u / amount_m if caps_ok and amount_m > 0 else None,
        "C_joint": cap_u / cap_m if caps_ok and cap_m > 0 else None,
        "Q": (amount_u / amount_m) / (cap_u / cap_m)
        if caps_ok and amount_m > 0 and cap_u > 0 and cap_m > 0 else None,
        "D": .5 * sum(abs(r.amount / amount_u - r.lag_float_cap / cap_u) for r in joint_u)
        if caps_ok and amount_u > 0 and cap_u > 0 else None,
        "U_plus": _amount(r for r in direction if r.return_ > 0) / direction_amount
        if _meets(amount_industry, .95) and _meets(direction_cov, .90)
        and direction_amount > 0 else None,
        "G": None,
        "B": None,
        "top5_amount_share": sum(sorted(active, reverse=True)[:ceil(.05 * len(active))]) / known
        if _meets(amount_industry, .95) and known > 0 else None,
        "amount_count_coverage_industry": amount_industry,
        "amount_count_coverage_market": amount_market,
        "joint_count_coverage_industry": cap_num_u,
        "joint_count_coverage_market": cap_num_m,
        "joint_amount_coverage_industry": cap_amt_u,
        "joint_amount_coverage_market": cap_amt_m,
        "direction_amount_coverage": direction_cov,
        "nonhead_return_coverage": None,
    }
    if head is not None:
        leaders = frozenset(head)
        head_rows = [r for r in segment if r.symbol in leaders]
        rest_rows = [r for r in segment if r.symbol not in leaders]
        head_joint, head_cov, _ = _cap_sample(head_rows)
        rest_joint, rest_cov, _ = _cap_sample(rest_rows)
        if (caps_ok and amount_u > 0 and cap_u > 0 and head_joint and rest_joint
                and _meets(head_cov, .95) and _meets(rest_cov, .95)):
            result["G"] = _amount(head_joint) / amount_u - _cap(head_joint) / cap_u
        nonhead_active = [r for r in rest_rows if r.amount and r.amount > 0]
        nonhead_returns = [r.return_ for r in nonhead_active if r.return_ is not None]
        breadth_cov = _coverage(len(nonhead_returns), len(nonhead_active))
        result["nonhead_return_coverage"] = breadth_cov
        if (_meets(_amount_coverage(rest_rows), .95)
                and _meets(breadth_cov, .90)):
            result["B"] = sum(x > 0 for x in nonhead_returns) / len(nonhead_returns)
    return result


def trailing_mean(values, window=5):
    """Includes current observation. NaN is invalid input, missing slots use None."""
    if window < 1:
        raise ValueError("window must be positive")
    selected = values[-window:]
    if len(selected) != window or any(x is None for x in selected):
        return None
    if any(not isfinite(x) for x in selected):
        raise ValueError("nonfinite rolling observation")
    return fmean(selected)


def historical_midrank(current, prior, window=252, minimum=200):
    """Prior sequence has one slot per trading date and excludes the signal day."""
    if not 1 <= minimum <= window:
        raise ValueError("minimum must be between one and window")
    if current is None:
        return None
    selected = [value for value in prior[-window:] if value is not None]
    if any(not isfinite(x) for x in (current, *selected)):
        raise ValueError("nonfinite rank observation")
    if len(selected) < minimum:
        return None
    step = Decimal("0.00000001")

    def round8(value):
        return Decimal(str(value)).quantize(step, rounding=ROUND_HALF_UP)

    level = round8(current)
    ordered = [round8(value) for value in selected]
    return 100 * (sum(x < level for x in ordered) + .5 * sum(x == level for x in ordered)) / len(ordered)
