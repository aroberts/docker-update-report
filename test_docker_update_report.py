import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
import unittest

# the script's filename has hyphens and no .py extension, so load it by path
# with an explicit loader; the __main__ guard means importing it has no side
# effects (no docker/skopeo calls)
SPEC_PATH = Path(__file__).with_name("docker-update-report")
loader = SourceFileLoader("docker_update_report", str(SPEC_PATH))
spec = importlib.util.spec_from_loader(loader.name, loader)
dur = importlib.util.module_from_spec(spec)
loader.exec_module(dur)


class TrueishTests(unittest.TestCase):
    def test_truthy_tokens(self):
        for v in ["true", "True", "T", "1", "y", "YES"]:
            self.assertIs(dur.trueish(v), True, v)

    def test_falsy_tokens(self):
        for v in ["false", "False", "F", "0", "n", "NO"]:
            self.assertIs(dur.trueish(v), False, v)

    def test_unrecognized_is_indeterminate(self):
        for v in [None, "", "maybe", "2"]:
            self.assertIsNone(dur.trueish(v), v)


class ResolveParseNumericsTests(unittest.TestCase):
    # a recognized boolean label wins outright, regardless of the CLI flag
    def test_label_true_enables_parsing(self):
        self.assertTrue(dur.resolve_parse_numerics("true", no_parse_numerics=False))
        self.assertTrue(dur.resolve_parse_numerics("true", no_parse_numerics=True))

    def test_label_false_disables_parsing(self):
        # regression: the old `not trueish(...)` inverted this and reported on
        self.assertFalse(dur.resolve_parse_numerics("false", no_parse_numerics=False))
        self.assertFalse(dur.resolve_parse_numerics("false", no_parse_numerics=True))

    # absent or unrecognized label falls through to the CLI flag
    def test_absent_label_uses_cli_default_on(self):
        # regression: the old logic never fell through, ignoring the CLI flag
        self.assertTrue(dur.resolve_parse_numerics(None, no_parse_numerics=False))

    def test_absent_label_honors_no_parse_numerics(self):
        self.assertFalse(dur.resolve_parse_numerics(None, no_parse_numerics=True))

    def test_unrecognized_label_falls_through(self):
        self.assertTrue(dur.resolve_parse_numerics("yarp", no_parse_numerics=False))
        self.assertFalse(dur.resolve_parse_numerics("yarp", no_parse_numerics=True))


if __name__ == "__main__":
    unittest.main()
