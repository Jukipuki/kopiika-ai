"""Unit tests for detect_mojibake() — Story 11.6."""

from app.services.format_detector import _MOJIBAKE_THRESHOLD, detect_mojibake


class TestDetectMojibake:
    def test_empty_list_returns_false(self):
        assert detect_mojibake([]) == (False, 0.0)

    def test_all_empty_strings_returns_false(self):
        assert detect_mojibake(["", "", ""]) == (False, 0.0)

    def test_all_clean_descriptions(self):
        flagged, rate = detect_mojibake(["COFFEE SHOP", "GROCERY", "Ресторан"])
        assert flagged is False
        assert rate == 0.0

    def test_over_threshold_flags_mojibake(self):
        # 10 chars, 2 U+FFFD → 20% > 5%
        flagged, rate = detect_mojibake(["ab\ufffdcd\ufffdefgh"])
        assert flagged is True
        assert rate > _MOJIBAKE_THRESHOLD

    def test_under_threshold_does_not_flag(self):
        # 100 chars, 2 U+FFFD → 2% < 5%
        desc = "a" * 98 + "\ufffd\ufffd"
        flagged, rate = detect_mojibake([desc])
        assert flagged is False
        assert rate == 0.02

    def test_exactly_at_threshold_does_not_flag(self):
        # Threshold is strictly >, so rate == 0.05 is not flagged
        # 100 chars, 5 U+FFFD → 5%
        desc = "a" * 95 + "\ufffd" * 5
        flagged, rate = detect_mojibake([desc])
        assert flagged is False
        assert rate == 0.05

    def test_just_over_threshold_flags(self):
        # 100 chars, 6 U+FFFD → 6% > 5%
        desc = "a" * 94 + "\ufffd" * 6
        flagged, rate = detect_mojibake([desc])
        assert flagged is True
        assert rate == 0.06

    def test_descriptions_with_empty_strings_mixed(self):
        # Empty strings contribute 0 chars; "\ufffd" is 1 of 1 char → 100%
        flagged, rate = detect_mojibake(["", "", "\ufffd"])
        assert flagged is True
        assert rate == 1.0

    def test_none_descriptions_via_empty_placeholder(self):
        # Caller is expected to pass "" for None — regression guard
        flagged, rate = detect_mojibake(["", "CLEAN TEXT"])
        assert flagged is False
        assert rate == 0.0
