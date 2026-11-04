import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'handheld'))
import stream_settings as settings
import moonlightctl


class StreamSettingsTests(unittest.TestCase):
    def test_all_profiles_are_valid_and_export_correct_units(self):
        for label, profile in settings.PROFILES.values():
            with self.subTest(profile=label):
                value = settings.validate(profile)
                exported = settings.environment(value)
                self.assertEqual(int(exported['RGSP_VIDEO_BITRATE_MAX']), value['video_kbps']*1000)
                self.assertEqual(int(exported['RGSP_AUDIO_BITRATE_MAX']), value['audio_kbps']*1000)
                self.assertEqual(settings.profile_name(value), label)

    def test_saved_preferences_survive_reload_and_leave_no_partial_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            fast = settings.PROFILES['fast'][1]
            settings.save(fast, path)
            self.assertEqual(settings.load(path), settings.validate(fast))
            self.assertEqual(list(Path(directory).iterdir()), [path])
            path.write_text('{invalid')
            self.assertEqual(settings.load(path), settings.defaults())

    def test_invalid_values_are_rejected_before_writing(self):
        for invalid in ({'video_kbps': 100000}, {'audio_kbps': True}, {'max_fps': 0},
                        {'version': 2}, {'audio_buffer_ms': -5}):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                settings.validate(invalid)

    def test_applying_without_active_service_only_saves(self):
        with mock.patch.object(moonlightctl, 'pid', return_value=None), \
             mock.patch.object(settings, 'load', return_value=settings.defaults()), \
             mock.patch.object(settings, 'save') as save, \
             mock.patch.object(moonlightctl, 'start') as start, \
             mock.patch.object(moonlightctl, 'stop') as stop:
            self.assertFalse(moonlightctl.apply_settings(settings.PROFILES['fast'][1]))
            save.assert_called_once()
            start.assert_not_called()
            stop.assert_not_called()

    def test_failed_restart_restores_previous_preferences(self):
        original = settings.defaults()
        with mock.patch.object(moonlightctl, 'pid', side_effect=[123, None]), \
             mock.patch.object(settings, 'load', return_value=original), \
             mock.patch.object(settings, 'save') as save, \
             mock.patch.object(moonlightctl, 'stop'), \
             mock.patch.object(moonlightctl, 'start', side_effect=[RuntimeError('failed'), None]) as start:
            with self.assertRaisesRegex(RuntimeError, 'restaurados'):
                moonlightctl.apply_settings(settings.PROFILES['fast'][1])
            self.assertEqual(save.call_args_list[-1].args[0], original)
            self.assertEqual(start.call_count, 2)


if __name__ == '__main__':
    unittest.main()
