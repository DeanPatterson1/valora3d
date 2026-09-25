"""Realism audit #13: a final render requires each world's photographic asset set; previews may fall back and
report it. The empty-library case points VALORA_ASSET_LIBRARY at an empty dir (as the fallback tests do)."""
import pytest

from engine.assets import library_root
from engine.world_assets import (AssetMissing, check_final_assets, courtyard_hdri, missing, required)

WORLDS = [("rain_courtyard", {"timeOfDay": "overcast_day"}), ("night_street", {"timeOfDay": "night"}),
          ("night_street", {"timeOfDay": "overcast_day"}), ("golden_field", {"timeOfDay": "golden"})]


def _script(wid, params):
    return {"world": {"id": wid, "params": params}}


def test_courtyard_final_takes_the_8k_sky():
    assert courtyard_hdri("final") == "cloudy_vondelpark_8k" and courtyard_hdri("preview") == "cloudy_vondelpark_4k"
    assert "cloudy_vondelpark_8k" in required("rain_courtyard", {}, "final")[0]
    assert "asphalt_02_disp" in required("rain_courtyard", {}, "final")[0]     # the shores need the scan height


def test_studio_needs_nothing():
    assert required("studio_cyc", {}, "final") == ((), ())
    assert check_final_assets(_script("studio_cyc", {}), "final") == []


@pytest.mark.parametrize("wid,params", WORLDS)
def test_empty_library_final_refuses_preview_reports(wid, params, tmp_path, monkeypatch):
    monkeypatch.setenv("VALORA_ASSET_LIBRARY", str(tmp_path))
    with pytest.raises(AssetMissing, match=wid):
        check_final_assets(_script(wid, params), "final")
    gone = check_final_assets(_script(wid, params), "preview")
    files, gltfs = required(wid, params, "preview")
    assert set(gone) == set(files) | set(gltfs)


@pytest.mark.skipif(not (library_root() / "polyhaven" / "cloudy_vondelpark_8k.hdr").exists(),
                    reason="the pinned library is not on this machine")
@pytest.mark.parametrize("wid,params", WORLDS)
def test_the_pinned_library_satisfies_every_final(wid, params):
    assert missing(wid, params, "final") == []
