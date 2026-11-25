import unittest

from factors.calculate import StockDay, daily_factors, freeze_head, historical_midrank, trailing_mean


def sample(amounts=(40, 30, 20, 10)):
    returns = (.02, -.01, -.01, .01)
    rows = [StockDay(code, "电子", amount, 10, change)
            for code, amount, change in zip("ABCD", amounts, returns)]
    return rows + [StockDay("M", None, 900, 360, .01)]


class CrowdingFactorsTest(unittest.TestCase):
    def test_same_heat_with_different_head_direction(self):
        for amounts, expected in [((40, 30, 20, 10), .20), ((10, 20, 30, 40), -.20)]:
            with self.subTest(amounts=amounts):
                result = daily_factors(sample(amounts), "电子", {"A", "B"})
                for metric, value in {"S": .1, "Q": 1, "D": .2, "G": expected,
                                      "B": .5, "U_plus": .5, "top5_amount_share": .4}.items():
                    self.assertAlmostEqual(result[metric], value)

    def test_market_and_industry_coverage_block_release(self):
        rows = sample()
        rows[0] = StockDay("A", "电子", None, 10, None)
        result = daily_factors(rows, "电子", {"A", "B"})
        self.assertEqual(result["amount_count_coverage_industry"], .75)
        self.assertIsNone(result["Q"])
        self.assertIsNone(result["G"])

    def test_excluded_cap_stock_still_in_raw_share(self):
        rows = [StockDay(f"X{i}", "电子", 10, 10, .01) for i in range(20)]
        rows += [StockDay("NEW", "电子", 1, None, .03, cap_eligible=False),
                 StockDay("MARKET", None, 800, 800, .02)]
        result = daily_factors(rows, "电子")
        self.assertAlmostEqual(result["S"], 201/1001)
        self.assertAlmostEqual(result["S_joint"], .20)
        self.assertEqual(result["Q"], 1)

    def test_missing_return_and_halt_are_distinct(self):
        rows = sample()
        rows[2] = StockDay("C", "电子", 0, 10, None)
        result = daily_factors(rows, "电子", {"A", "B"})
        self.assertEqual(result["B"], 1)
        rows[2] = StockDay("C", "电子", 20, 10, None)
        result = daily_factors(rows, "电子", {"A", "B"})
        self.assertIsNone(result["B"])
        self.assertIsNone(result["U_plus"])

    def test_freeze_coverage_tie_and_calendar(self):
        common = {"A": [5] * 20, "B": [5] * 20, "C": [4] * 20}
        self.assertEqual(freeze_head(["C", "B", "A"], common), {"A"})
        self.assertIsNone(freeze_head("ABCD", common))
        with self.assertRaises(ValueError):
            freeze_head("AB", {"A": [5] * 19})

    def test_strict_rolling_mean_and_midrank(self):
        self.assertIsNone(trailing_mean([1, 1, None, 1, 1]))
        self.assertEqual(trailing_mean([0, 1, 2, 3, 4, 5]), 3)
        self.assertEqual(historical_midrank(1, [0] + [1] * 252), 50)
        self.assertEqual(historical_midrank(1, [.6, 1, 1, 1.2], 4, 4), 50)
        self.assertIsNone(historical_midrank(1, [1.0] * 199))
        self.assertIsNone(historical_midrank(1, [1.0] * 200 + [None] * 53))

    def test_rejects_duplicate_symbols(self):
        rows = sample()
        with self.assertRaises(ValueError):
            daily_factors(rows + [rows[0]], "电子")
