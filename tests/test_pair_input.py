"""Regression checks for handheld and Bluetooth pad PIN confirmation."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'handheld'))
from pair_ui import button_actions


class PairInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def config(self, filename, name, guid, a, b, start=9):
        path = self.root / filename
        path.write_text(
            f'<inputList><inputConfig deviceName="{name}" deviceGUID="{guid}">'
            f'<input name="a" type="button" id="{a}" value="1"/>'
            f'<input name="b" type="button" id="{b}" value="1"/>'
            f'<input name="start" type="button" id="{start}" value="1"/>'
            '</inputConfig></inputList>'
        )
        return path

    def test_confirm_uses_configured_a_not_button_zero(self):
        cfg = self.config('input.xml', 'Handheld', 'abc', a=5, b=0)
        actions = button_actions('Handheld', 'abc', [cfg])
        self.assertEqual(actions[5], 'ok')
        self.assertEqual(actions[0], 'back')
        self.assertEqual(actions[9], 'ok')

    def test_external_pad_uses_its_own_guid_mapping(self):
        handheld = self.config('handheld.xml', 'Gamepad', '111', a=5, b=0)
        bluetooth = self.config('bluetooth.xml', 'Gamepad', '222', a=1, b=2)
        actions = button_actions('Gamepad', '222', [handheld, bluetooth])
        self.assertEqual(actions[1], 'ok')
        self.assertEqual(actions[2], 'back')
        self.assertNotIn(5, actions)

    def test_user_mapping_takes_precedence_for_same_guid(self):
        user = self.config('user.xml', 'Pad', 'ABC', a=4, b=3)
        system = self.config('system.xml', 'Pad', 'abc', a=0, b=1)
        actions = button_actions('Pad', 'abc', [user, system])
        self.assertEqual(actions[4], 'ok')
        self.assertEqual(actions[3], 'back')

    def test_shared_guid_prefers_the_actual_device_name(self):
        other = self.config('other.xml', 'Other handheld', 'same', a=0, b=1)
        actual = self.config('actual.xml', 'RG35XXSP', 'same', a=3, b=4)
        actions = button_actions('RG35XXSP', 'same', [other, actual])
        self.assertEqual(actions[3], 'ok')
        self.assertEqual(actions[4], 'back')

    def test_unreadable_or_unmatched_config_keeps_legacy_fallback(self):
        broken = self.root / 'broken.xml'
        broken.write_text('<invalid')
        self.assertEqual(button_actions('Unknown', 'none', [broken]), {0: 'ok', 1: 'back'})


if __name__ == '__main__':
    unittest.main()
