"""measure.py never scores a lexicon on the gold that supplied it."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import measure  # noqa: E402


def test_infopedia_refuses_the_board_dataset_that_holds_it():
    assert measure.supplying_datasets("infopedia") == {
        "infopedia", "portuguese_unified", "portuguese_unified_corrected"}


def test_wikipron_refuses_itself():
    assert measure.supplying_datasets("wikipron") == {"wikipron", "wikipron_corrected"}
