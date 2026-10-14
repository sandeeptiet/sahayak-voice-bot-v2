import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sahayak.intake import Category, Priority, assign_priority, validate_callback_time


class IntakeTests(unittest.TestCase):
    def test_category_baselines(self):
        expected = {
            "account_access": "high", "network": "high", "vpn": "medium",
            "microsoft_365": "medium", "hardware": "medium", "other": "medium",
            "software": "low",
        }
        for category, priority in expected.items():
            with self.subTest(category=category):
                self.assertEqual(assign_priority(category, "Please help"), priority)

    def test_multiple_urgency_phrases_raise_only_one_level(self):
        self.assertEqual(assign_priority(Category.SOFTWARE, "URGENT: cannot work"), Priority.MEDIUM)
        self.assertEqual(assign_priority(Category.NETWORK, "critical, down"), Priority.CRITICAL)

    def test_unknown_category_is_not_silently_defaulted(self):
        with self.assertRaises(ValueError):
            assign_priority("unrecognized", "Please help")

    def test_preserves_documented_substring_baseline(self):
        self.assertEqual(assign_priority("software", "download issue"), Priority.MEDIUM)

    def test_indian_callback_normalizes_to_utc(self):
        requested = datetime(2026, 10, 12, 10, tzinfo=ZoneInfo("Asia/Kolkata"))
        now = datetime(2026, 10, 12, 4, tzinfo=timezone.utc)
        self.assertEqual(validate_callback_time(requested, now=now), now + timedelta(minutes=30))
        self.assertIs(validate_callback_time(requested, now=now).tzinfo, timezone.utc)

    def test_past_equal_and_naive_times_rejected(self):
        now = datetime(2026, 10, 12, 4, tzinfo=timezone.utc)
        for requested in (now, now - timedelta(seconds=1), now.replace(tzinfo=None)):
            with self.subTest(requested=requested), self.assertRaises(ValueError):
                validate_callback_time(requested, now=now)
        with self.assertRaises(ValueError):
            validate_callback_time(now + timedelta(hours=1), now=now.replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()
