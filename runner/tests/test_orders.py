import unittest

from eval.baseline import FailureSignature, RunOutcome, TestIdentifier
from eval.tests.fake_runner import FakeOrderRunner
from runner.orders import class_first_shuffle, distinct_shuffles, search_orders

V = TestIdentifier("pkg.AVictimTest", "v")
REAL = RunOutcome(passed=False, failure_signature=FailureSignature("java.lang.AssertionError", "x:1", "m"))
CRASH = RunOutcome(passed=False, failure_signature=FailureSignature("flaketrace.JvmCrash", "", "code 1"))
PASS = RunOutcome(passed=True)


def suite(classes=4, methods=2):
    tests = [TestIdentifier(f"pkg.C{c}Test", f"m{m}") for c in range(classes) for m in range(methods)]
    return tests + [V]


class TestShuffle(unittest.TestCase):
    def test_methods_of_a_class_stay_together(self):
        for seed in range(20):
            order = class_first_shuffle(suite(), seed)
            classes = [t.class_name for t in order]
            runs = [c for i, c in enumerate(classes) if i == 0 or c != classes[i - 1]]
            self.assertEqual(len(runs), len(set(runs)), order)

    def test_same_seed_same_order_and_nothing_lost(self):
        self.assertEqual(class_first_shuffle(suite(), 7), class_first_shuffle(suite(), 7))
        self.assertEqual(sorted(class_first_shuffle(suite(), 7), key=str), sorted(suite(), key=str))

    def test_different_seeds_give_different_orders(self):
        self.assertGreater(len({tuple(class_first_shuffle(suite(), s)) for s in range(10)}), 1)

    def test_orders_are_cut_after_the_victim_and_distinct(self):
        shuffles, _ = distinct_shuffles(suite(), V, budget=10, seed_base=0)
        self.assertEqual(len(shuffles), 10)
        self.assertTrue(all(order[-1] == V for _, order in shuffles))
        self.assertEqual(len({tuple(order) for _, order in shuffles}), 10)

    def test_small_suite_is_exhausted_honestly(self):
        two = [TestIdentifier("pkg.BTest", "b"), V]
        shuffles, exhausted = distinct_shuffles(two, V, budget=31, seed_base=0)
        # The starting order [B, V] already ran; only [V] is a new order.
        self.assertEqual([tuple(o) for _, o in shuffles], [(V,)])
        self.assertTrue(exhausted)

    def test_the_starting_order_is_never_counted_as_a_shuffle(self):
        start = suite(classes=3, methods=1)
        shuffles, _ = distinct_shuffles(start, V, budget=31, seed_base=0)
        self.assertNotIn(tuple(start), [tuple(o) for _, o in shuffles])

    def test_victim_first_shuffle_is_a_distinct_order(self):
        shuffles, _ = distinct_shuffles(suite(classes=3, methods=1), V, budget=31, seed_base=0)
        self.assertIn((V,), [tuple(o) for _, o in shuffles])

    def test_seeds_are_consecutive_from_the_base(self):
        shuffles, _ = distinct_shuffles(suite(), V, budget=5, seed_base=100)
        self.assertEqual(shuffles[0][0], 100)
        self.assertTrue(all(a < b for (a, _), (b, _) in zip(shuffles, shuffles[1:])))


class TestSearchOrders(unittest.TestCase):
    def test_first_real_failure_wins_and_crashes_do_not_count(self):
        candidates = [(0, [V]), (1, [TestIdentifier("pkg.ZTest", "z"), V]), (2, [V])]
        outcomes = iter([CRASH, REAL, REAL])
        runner = FakeOrderRunner(lambda order, test: next(outcomes) if test == V else PASS)
        seed, order, reference, runs, any_failures = search_orders(runner, candidates, V)
        self.assertEqual((seed, order, runs, any_failures), (1, candidates[1][1], 2, 2))
        self.assertEqual(reference.exception_type, "java.lang.AssertionError")

    def test_nothing_fails(self):
        runner = FakeOrderRunner(lambda order, test: PASS)
        self.assertEqual(search_orders(runner, [(0, [V]), (1, [V])], V), (None, None, None, 2, 0))


if __name__ == "__main__":
    unittest.main()
