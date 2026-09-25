"""AssureX master test runner — runs every automated suite.
Manual/UI test cases are documented in documentation/test_cases.md."""
import sys

SUITES = ["tests.test_rule_engine", "tests.test_models",
          "tests.test_ocr_fraud"]


def main():
    total_fail = 0
    for name in SUITES:
        print(f"\n{'=' * 60}\nRUNNING {name}\n{'=' * 60}")
        mod = __import__(name, fromlist=["run"])
        try:
            if not mod.run():
                total_fail += 1
        except Exception as e:
            print(f"[ERROR] suite crashed: {e}")
            total_fail += 1
    print(f"\n{'=' * 60}")
    print("ALL SUITES DONE —",
          "ALL PASSED [OK]" if total_fail == 0
          else f"{total_fail} suite(s) FAILED")
    return total_fail == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)