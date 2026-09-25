"""Review 6 #8 on harness/director_eval.py: a scaled subject re-derives its size-dependent vehicle class
(the ingest rule on the scaled length and the ride-height / wheel-radius facts), never keeps the stored label."""
import dataclasses

from harness import director_eval as de


# ---- #8: vehicleClass follows the scaled size ---------------------------------------------------------------
def test_shrinking_a_sports_car_below_toy_length_makes_it_a_toy():
    p = de._profile("sports_car")
    assert p.vehicle["vehicleClass"] == "sport"
    assert de.scaled_profile(p, 0.5).vehicle["vehicleClass"] == "toy"


def test_a_toy_scaled_to_full_size_takes_its_ride_height_class():
    p = de._profile("sports_car")
    from engine.ingest.measure import VEHICLE_TOY_M
    toy = de.scaled_profile(p, 0.5 * VEHICLE_TOY_M)
    assert toy.vehicle["vehicleClass"] == "toy"
    # the ride height / wheel radius ratio is scale-free, so the full-size car is the sports car again
    assert de.scaled_profile(toy, p.longest).vehicle["vehicleClass"] == "sport"


def test_the_class_uses_the_ingest_ride_height_rule_not_the_stored_label():
    p = de._profile("sports_car")
    r = sorted(w["radius"] for w in p.wheels)[len(p.wheels) // 2]
    tall = dataclasses.replace(p, vehicle={**p.vehicle, "rideHeightM": 0.95 * r, "vehicleClass": "toy"})
    assert de.scaled_profile(tall, 2 * p.longest).vehicle["vehicleClass"] == "offroad"


def test_unit_scale_keeps_every_vehicle_fact():
    p = de._profile("sports_car")
    assert de.scaled_profile(p, p.longest).vehicle == p.vehicle
