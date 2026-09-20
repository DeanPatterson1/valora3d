"""The render camera must trace the same path the viewer draws.

Every expected number here is also asserted, to the same precision, by
`apps/web/components/viewer/cameraParity.test.ts`. If a change makes one file
fail, the other is wrong too: the preview and the video would disagree.
"""
import math
import unittest

import scene_plan_camera as camera


def plan(**over):
    base = {
        "camera": {"style": "smooth", "lensMm": 50, "heightM": 1.4, "motionStrength": 0.0},
        "effects": {"rain": 0.0, "wetGround": 0.0, "motionBlur": 0.0, "depthOfField": 0.0},
        "shots": [
            {"id": "a", "start": 0, "end": 4, "action": "slow_orbit", "distanceMultiplier": 1.0},
            {"id": "b", "start": 4, "end": 10, "action": "hero_push_in", "distanceMultiplier": 1.0},
        ],
    }
    base.update(over)
    return base


SUBJECT = {"radius": 2.4, "height": 1.45}


class Bounds(unittest.TestCase):
    def test_reads_ground_radius_and_height(self):
        self.assertEqual(camera.bounds((4.8, 2.1, 1.45)), {"radius": 2.4, "height": 1.45})

    def test_radius_takes_the_wider_ground_axis(self):
        self.assertEqual(camera.bounds((2.0, 6.0, 1.0))["radius"], 3.0)


class ShotAt(unittest.TestCase):
    def test_finds_the_running_shot(self):
        shot, t = camera.shot_at(plan(), 1.0)
        self.assertEqual(shot["id"], "a")
        self.assertAlmostEqual(t, 0.25)

    def test_clamps_before_the_first_shot(self):
        shot, t = camera.shot_at(plan(), -5.0)
        self.assertEqual(shot["id"], "a")
        self.assertEqual(t, 0.0)

    def test_clamps_past_the_last_shot(self):
        shot, t = camera.shot_at(plan(), 99.0)
        self.assertEqual(shot["id"], "b")
        self.assertEqual(t, 1.0)

    def test_a_boundary_belongs_to_the_earlier_shot(self):
        shot, _ = camera.shot_at(plan(), 4.0)
        self.assertEqual(shot["id"], "a")


class PathPoints(unittest.TestCase):
    def test_slow_orbit_start(self):
        point = camera.shot_path_point(plan(), plan()["shots"][0], 0.0, SUBJECT)
        self.assertAlmostEqual(point[0], -6.788225099390855, places=12)
        self.assertAlmostEqual(point[1], 1.4, places=12)
        self.assertAlmostEqual(point[2], 6.788225099390856, places=12)

    def test_hero_push_in_moves_closer(self):
        shot = plan()["shots"][1]
        start = camera.shot_path_point(plan(), shot, 0.0, SUBJECT)
        end = camera.shot_path_point(plan(), shot, 1.0, SUBJECT)
        self.assertGreater(math.hypot(start[0], start[2]), math.hypot(end[0], end[2]))

    def test_low_tracking_is_capped_below_eye_height(self):
        shot = {"id": "c", "start": 0, "end": 1, "action": "low_tracking", "distanceMultiplier": 1.0}
        self.assertAlmostEqual(camera.shot_path_point(plan(), shot, 0.5, SUBJECT)[1], 0.6)

    def test_a_longer_lens_backs_off(self):
        shot = plan()["shots"][0]
        near = camera.shot_path_point(plan(), shot, 0.0, SUBJECT)
        far = camera.shot_path_point(plan(camera={"style": "smooth", "lensMm": 100, "heightM": 1.4, "motionStrength": 0.0}), shot, 0.0, SUBJECT)
        self.assertGreater(math.hypot(far[0], far[2]), math.hypot(near[0], near[2]))

    def test_rejects_an_unknown_action(self):
        shot = {"id": "x", "start": 0, "end": 1, "action": "barrel_roll", "distanceMultiplier": 1.0}
        with self.assertRaises(camera.PlanError):
            camera.shot_path_point(plan(), shot, 0.0, SUBJECT)


class Handheld(unittest.TestCase):
    def test_is_still_at_zero_strength(self):
        self.assertEqual(camera.handheld_offset(3.0, 0.0), ((0.0, 0.0, 0.0), 0.0))

    def test_sways_on_absolute_time(self):
        sway, roll = camera.handheld_offset(2.0, 1.0)
        self.assertAlmostEqual(sway[0], math.sin(2.0 * 7.3) * 0.02, places=12)
        self.assertAlmostEqual(sway[1], abs(math.sin(2.0 * 5.1)) * 0.03, places=12)
        self.assertAlmostEqual(roll, math.sin(2.0 * 2.1) * 0.01, places=12)

    def test_vertical_sway_never_dips(self):
        for step in range(50):
            self.assertGreaterEqual(camera.handheld_offset(step / 7, 1.0)[0][1], 0.0)


class Lens(unittest.TestCase):
    def test_fifty_millimetres(self):
        self.assertAlmostEqual(camera.lens_to_fov(50), 26.991466561591626, places=12)

    def test_twenty_four_millimetres(self):
        self.assertAlmostEqual(camera.lens_to_fov(24), 53.13010235415598, places=12)

    def test_aperture_spans_deep_to_shallow(self):
        self.assertEqual(camera.aperture(0), 16.0)
        self.assertAlmostEqual(camera.aperture(1), 1.8, places=12)
        self.assertAlmostEqual(camera.aperture(5), 1.8, places=12)
        self.assertLess(camera.aperture(1), camera.aperture(0.5))


class Axes(unittest.TestCase):
    def test_gltf_y_up_becomes_blender_z_up(self):
        self.assertEqual(camera.to_blender((1, 2, 3), (0, 0, 0)), (1, -3, 2))

    def test_offsets_from_the_subject_ground_centre(self):
        self.assertEqual(camera.to_blender((1, 2, 3), (10, 20, 30)), (11, 17, 32))

    def test_pose_aims_at_the_middle_of_the_subject(self):
        _, aim, _ = camera.pose(plan(), SUBJECT, (0, 0, 0), 0.0)
        self.assertEqual(aim, (0, 0, SUBJECT["height"] / 2))


if __name__ == "__main__":
    unittest.main()
