import unittest

from material_classes import classify


class ClassifyTests(unittest.TestCase):
    def test_runtime_names_win_without_slots(self):
        self.assertEqual(classify('mv-unified-paint.003'), 'paint')
        self.assertEqual(classify('mv-carbon-weave (was Carbon Fiber Glossy)'), 'carbon')
        self.assertEqual(classify('mv-window-tint'), 'privacy-glass')
        self.assertEqual(classify('mv-smoke-lens'), 'lamp-lens')
        self.assertEqual(classify('rubber'), 'rubber')

    def test_authored_family_is_known_by_name(self):
        self.assertEqual(classify('MV_HeadlightGlass'), 'lamp-lens')
        self.assertEqual(classify('MV_TailGlass'), 'lamp-lens')
        self.assertEqual(classify('MV_WindowTint'), 'privacy-glass')
        self.assertEqual(classify('MV_TireRubber'), 'rubber')
        self.assertEqual(classify('MV_WheelTire.001'), 'rubber')
        self.assertIsNone(classify('MV_LampHousing'))
        self.assertIsNone(classify('MV_Chrome', {'headlight-L'}, metallic=1.0))

    def test_artist_names_need_the_slot_tag(self):
        self.assertIsNone(classify('Headlight Glass'))                                   # untagged snapshot: untouched
        self.assertEqual(classify('Headlight Glass', {'headlight-L', 'headlight-R'}), 'lamp-lens')
        self.assertEqual(classify('Red Glass', {'taillight-L'}, alpha=0.4), 'lamp-lens')
        self.assertEqual(classify('headlight', {'headlight-L'}, alpha=0.3), 'lamp-lens')   # transparent proves it
        self.assertIsNone(classify('headlight', {'headlight-L'}))                        # opaque housing stays
        self.assertIsNone(classify('lamp-housing', {'headlight-L'}, alpha=1.0))
        self.assertEqual(classify('Window', {'windshield', 'side-windows'}), 'privacy-glass')
        self.assertEqual(classify('Glass Darker', {'rear-window'}, alpha=0.6), 'privacy-glass')
        self.assertIsNone(classify('Glass Darker', {'rear-window', 'door-L'}))            # shared with a body slot
        self.assertEqual(classify('Tire', {'tire-FL', 'tire-RR'}), 'rubber')
        self.assertIsNone(classify('Tire', {'tire-FL', 'wheel-FL'}))
        self.assertIsNone(classify('Alloy', {'tire-FL'}, metallic=1.0))


if __name__ == '__main__':
    unittest.main()
