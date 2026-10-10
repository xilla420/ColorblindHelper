import unittest

from colorblind_helper.colors import (ciede2000, color_info, contrast_ratio, describe,
                                      nearest_named_color, simulate_cvd)


class ColorTests(unittest.TestCase):
    def test_ciede2000_reference(self):
        # Sharma et al. test pair #1
        self.assertAlmostEqual(ciede2000((50, 2.6772, -79.7751), (50, 0, -82.7485)), 2.0425, 3)

    def test_exact_names(self):
        for rgb, name in [((255, 0, 0), "Red"), ((70, 130, 180), "Steel Blue"),
                          ((210, 180, 140), "Tan"), ((0, 128, 128), "Teal")]:
            self.assertEqual(nearest_named_color(rgb)[0], name)

    def test_descriptions(self):
        cases = {(0, 0, 0): "Black", (255, 255, 255): "White", (128, 128, 128): "Gray",
                 (139, 69, 19): "Dark brown", (0, 0, 128): "Navy", (220, 20, 60): "Vivid red",
                 (255, 230, 230): "Pale pink", (245, 245, 220): "Beige"}
        for rgb, text in cases.items():
            self.assertEqual(describe(rgb), text, rgb)

    def test_simulation_red_green_confusion(self):
        red, green = simulate_cvd((255, 0, 0), "deutan"), simulate_cvd((0, 128, 0), "deutan")
        # Red and green become far closer for a deutan observer.
        d = sum(abs(a - b) for a, b in zip(red, green))
        self.assertLess(d, 260)
        self.assertEqual(len(set(simulate_cvd((200, 50, 50), "achroma"))), 1)

    def test_contrast(self):
        self.assertAlmostEqual(contrast_ratio((0, 0, 0), (255, 255, 255)), 21.0, 1)

    def test_info_has_all_simulations(self):
        kinds = [k for k, _, _ in color_info((10, 200, 30)).simulations]
        self.assertEqual(kinds, ["protan", "deutan", "tritan", "achroma"])


if __name__ == "__main__":
    unittest.main()
