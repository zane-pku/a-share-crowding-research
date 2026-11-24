"""Crowding research arithmetic. Run with --self-test or --scenario 0-4."""
import argparse
import json
import math

# (sector turnover, market turnover, float-cap share %, daily turnover, position, participation %)
SCENARIOS = (
    ("基准", (100, 1000, 10, 20, 10, 10)),
    ("板块放量", (150, 1000, 10, 25, 10, 10)),
    ("市场缩量", (100, 700, 10, 20, 10, 10)),
    ("行业体量扩张", (150, 1000, 15, 25, 10, 10)),
    ("承接收缩", (100, 1000, 10, 8, 10, 5)),
)


def review(sector, market, cap_pct, adv, position, participation_pct):
    values = (sector, market, cap_pct, adv, position, participation_pct)
    if not all(math.isfinite(x) for x in values):
        raise ValueError("数字必须有限")
    if not 0 < sector <= market or not 0 < cap_pct <= 100:
        raise ValueError("成交额及市值份额不满足同池约束")
    if not adv > 0 or position < 0 or not 0 < participation_pct <= 100:
        raise ValueError("退出容量输入无效")
    share = sector / market
    relative = share / (cap_pct / 100)
    return {"成交份额": share, "相对换手": relative,
            "退出容量天数": position / (adv * participation_pct / 100)}


def research_example():
    """Five synthetic days and an eight-observation rank example."""
    raw = []
    for index in range(5):
        amounts = (32 + 2 * index, 30, 20, 18 - 2 * index)
        total = sum(amounts)
        share = total / 1000
        relative = share / (40 / 400)
        deviation = .5 * sum(abs(value / total - .25) for value in amounts)
        up_share = (amounts[0] + amounts[2]) / total
        raw.append((relative, deviation, up_share))
    history = (
        (.60, .75, .90, 1, 1, 1.05, 1.20, 1.40),
        (.04, .06, .08, .10, .12, .14, .16, .20),
        (.35, .40, .45, .50, .50, .55, .60, .65),
    )
    means = tuple(round(sum(column) / 5, 8) for column in zip(*raw))
    ranks = tuple(100 * (sum(x < v for x in h) + .5 * sum(x == v for x in h)) / len(h)
                  for v, h in zip(means, history))
    return {"daily": raw, "mean": means, "rank": ranks, "score": sum(ranks) / 3}



def direction_example():
    records = []
    for amounts in [(40, 30, 20, 10), (10, 20, 30, 40)]:
        total = sum(amounts)
        share = total / 1000
        weights = [value / total for value in amounts]
        records.append({
            "share": share,
            "relative_turnover": share / (40 / 400),
            "absolute_deviation": .5 * sum(abs(weight - .25) for weight in weights),
            "up_turnover": weights[0] + weights[3],
            "head_weight": sum(weights[:2]),
            "head_excess_pp": round(100 * (sum(weights[:2]) - .5), 8),
        })
    return records



def self_test():
    left, right = direction_example()
    assert (left["head_excess_pp"], right["head_excess_pp"]) == (20, -20)
    for metric in ("share", "relative_turnover", "absolute_deviation", "up_turnover"):
        assert math.isclose(left[metric], right[metric])
    example = research_example()
    assert example['mean'] == (1, .16, .56)
    assert example['rank'] == (50, 81.25, 75)
    assert example['score'] == 68.75
    results = [review(*values) for _, values in SCENARIOS]
    targets = [(0.1, 1, 5), (.15, 1.5, 4), (1/7, 10/7, 5), (.15, 1, 4), (.1, 1, 25)]
    for actual, expected in zip(results, targets):
        assert all(math.isclose(a, e) for a, e in zip(actual.values(), expected))
    base = results[0]
    for (_, values), result in zip(SCENARIOS, results):
        lhs = math.log(result["成交份额"] / base["成交份额"])
        rhs = math.log(values[2] / SCENARIOS[0][1][2]) + math.log(result["相对换手"] / base["相对换手"])
        assert math.isclose(lhs, rhs, abs_tol=1e-12)
    try:
        review(101, 100, 10, 20, 10, 10)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid denominator accepted")
    print("PASS: five teaching scenarios, decomposition and pool constraint")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    controls = parser.add_mutually_exclusive_group()
    controls.add_argument("--self-test", action="store_true")
    controls.add_argument("--scenario", type=int, choices=range(len(SCENARIOS)))
    controls.add_argument("--export-demo", action="store_true", help="print synthetic inputs as JSON")
    controls.add_argument("--research-example", action="store_true")
    controls.add_argument("--direction-example", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    elif args.direction_example:
        print(json.dumps(direction_example(), indent=2))
    elif args.research_example:
        print(json.dumps(research_example(), indent=2))
    elif args.export_demo:
        print(json.dumps(SCENARIOS, ensure_ascii=True))
    else:
        name, values = SCENARIOS[args.scenario if args.scenario is not None else 0]
        print(json.dumps({"情景": name, **review(*values)}, ensure_ascii=True, indent=2))
