import os
import unittest

from colorblind_helper.paintings import GALLERY, PAINTINGS, asset_path
from colorblind_helper.settings import Settings
from colorblind_helper.themes import THEMES, get_theme


class AppDataTests(unittest.TestCase):
    def test_every_painting_asset_exists(self):
        for key in PAINTINGS:
            self.assertTrue(os.path.exists(asset_path("paintings", f"{key}.jpg")), key)

    def test_themes_reference_real_paintings(self):
        for t in THEMES.values():
            if t.painting:
                self.assertIn(t.painting, PAINTINGS)
        self.assertTrue(set(GALLERY) <= set(PAINTINGS))

    def test_legacy_theme_keys_migrate(self):
        s = Settings()
        s.update_from({"ui_theme": "sakura", "overlay_theme": "midnight"})
        self.assertEqual((s.ui_theme, s.overlay_theme), ("almond", "charcoal"))
        self.assertEqual(get_theme("daylight").key, "linen")

    def test_palette_dedupes_newest_first_and_caps(self):
        s = Settings()
        for i in range(50):
            s.add_to_palette(f"#{i:06X}")
        s.add_to_palette("#000031")  # existing -> moves to front
        self.assertEqual(s.palette[0], "#000031")
        self.assertEqual(len(s.palette), Settings.PALETTE_MAX)
        self.assertEqual(len(set(s.palette)), len(s.palette))

    def test_reset_keeps_palette(self):
        s = Settings()
        s.add_to_palette("#123456")
        s.ui_theme = "irises"
        s.reset()
        self.assertEqual(s.palette, ["#123456"])
        self.assertEqual(s.ui_theme, "starry")


if __name__ == "__main__":
    unittest.main()
