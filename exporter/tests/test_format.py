"""Round-trip and frame-convention tests for the Unreal export.

Run with `python -m pytest exporter/tests -q` from the repo root, or
`python exporter/tests/test_format.py` for a dependency-free run.

The conversion tests are the load-bearing ones. A mirrored map looks entirely
plausible, so the y-negation gets its own named test the way
`tests/test_frame_convention.py` does for the vrgrid frames themselves.
"""

import json
import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vrgrid_unreal import format as F                      # noqa: E402
from vrgrid_unreal import convert as C                     # noqa: E402
from vrgrid_unreal import provenance as P                  # noqa: E402


def test_roundtrip_preserves_header_and_every_chunk():
    chunks = {
        b"PNTS": F.pack_points([[1, 2, 3], [4, 5, 6]], [[255, 0, 0], [0, 255, 0]]),
        b"GHST": F.pack_points([[7, 8, 9]], [[255, 0, 255]]),
        b"OCCU": F.pack_cells([1.0, 2.0], [2.0, 3.0], [3.0, 4.0], [0.05, 0.40],
                              [[10, 20, 30, 255], [40, 50, 60, 200]]),
        b"CURB": F.pack_boxes([[1, 1, 1]], [[0.05, 0.05, 0.06]], [[230, 159, 0, 235]]),
        b"TRAJ": F.pack_vec3([[0, 0, 0], [1, 0, 0]]),
    }
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "000042.vrgf")
        F.write_frame(p, 42, (1.5, -2.5, 0.25), 0.75, 4.2, chunks)
        header, got = F.read_frame(p)

    assert header["frame_index"] == 42
    assert np.allclose(header["vehicle_xyz"], (1.5, -2.5, 0.25))
    assert abs(header["vehicle_yaw"] - 0.75) < 1e-6
    assert set(got) == set(chunks)
    for cid, arr in chunks.items():
        assert np.array_equal(got[cid], arr), cid


def test_empty_layer_is_written_not_dropped():
    """An empty layer must survive as count 0. A reader that saw the chunk
    missing would leave the previous frame's instances on screen, which is how
    a ghost trail outlives the cleanup that removed it."""
    chunks = {b"OCCU": F.pack_cells([], [], [], [], np.zeros((0, 4), np.uint8))}
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "f.vrgf")
        F.write_frame(p, 0, (0, 0, 0), 0.0, 0.0, chunks)
        _, got = F.read_frame(p)
    assert b"OCCU" in got and len(got[b"OCCU"]) == 0


def test_sigma_travels_per_cell():
    """Accuracy is per cell, and 0 means "not reported" rather than "certain"."""
    arr = F.pack_cells([0, 1.0], [0, 0], [0, 0], [0.05, 0.40],
                       np.zeros((2, 4), np.uint8), sigma_cm=[1.2, 31.5])
    assert abs(float(arr["sigma_cm"][0]) - 1.2) < 1e-4
    assert abs(float(arr["sigma_cm"][1]) - 31.5) < 1e-4
    bare = F.pack_cells([0.0], [0], [0], [0.05], np.zeros((1, 4), np.uint8))
    assert float(bare["sigma_cm"][0]) == 0.0


def test_cell_size_travels_per_item():
    """5 cm and 40 cm cells in one chunk come back distinguishable -- the
    foveation is only visible because the size is per cell, not per chunk."""
    arr = F.pack_cells([0, 100.0], [0, 0], [0, 0], [0.05, 0.40],
                       np.zeros((2, 4), np.uint8))
    assert arr["cell_m"][0] == np.float32(0.05)
    assert arr["cell_m"][1] == np.float32(0.40)


def test_unknown_chunk_ids_are_skipped_by_length():
    """Forward compatibility: a reader that does not know an id must step over
    it and keep going, or adding a layer becomes a C++ rebuild."""
    import struct
    chunks = {b"PNTS": F.pack_points([[1, 2, 3]], [[1, 2, 3]])}
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "f.vrgf")
        F.write_frame(p, 7, (0, 0, 0), 0.0, 0.0, chunks)
        raw = bytearray(open(p, "rb").read())
        # Splice in a chunk nobody knows, and bump the count.
        payload = b"\xde\xad\xbe\xef" * 4
        raw += struct.pack("<4sIII", b"XXXX", 4, 4, len(payload)) + payload
        raw[12:16] = struct.pack("<I", 2)
        open(p, "wb").write(bytes(raw))
        header, got = F.read_frame(p)
    assert header["frame_index"] == 7
    assert set(got) == {b"PNTS"}


# --- the frame convention ----------------------------------------------------


def test_left_is_negative_y_in_unreal():
    """THE test. VRgrid +y is LEFT; Unreal +y is RIGHT. Drop this negation and
    every scene is its own mirror image and still looks correct."""
    out = C.xyz_to_unreal([[0.0, 1.0, 0.0]])
    assert np.allclose(out, [[0.0, -100.0, 0.0]])


def test_forward_and_up_are_unchanged_but_scaled():
    assert np.allclose(C.xyz_to_unreal([[1.0, 0, 0]]), [[100.0, 0, 0]])
    assert np.allclose(C.xyz_to_unreal([[0, 0, 1.0]]), [[0, 0, 100.0]])


def test_metres_to_centimetres():
    assert np.allclose(C.length_to_unreal(0.05), 5.0)
    assert np.allclose(C.length_to_unreal(0.40), 40.0)


def test_yaw_sign_flips_with_handedness():
    assert abs(C.yaw_to_unreal_deg(np.pi / 2) - (-90.0)) < 1e-9
    assert abs(C.yaw_to_unreal_deg(0.0)) < 1e-9


def test_manifest_vectors_match_the_converter():
    """What the C++ reader checks itself against at load."""
    for v in C.conversion_test_vectors():
        assert np.allclose(C.xyz_to_unreal([v["m"]])[0], v["cm"])


def test_conversion_vectors_would_catch_a_sign_error_on_any_axis():
    """The vectors are only a guard if flipping any one axis breaks one of
    them. Check that directly rather than trusting the choice."""
    vecs = C.CONVERSION_TEST_VECTORS_M
    good = C.xyz_to_unreal(vecs)
    for axis in range(3):
        wrong = good.copy()
        wrong[:, axis] *= -1.0
        assert not np.allclose(wrong, good), f"axis {axis} flip is invisible"


# --- provenance --------------------------------------------------------------
#
# A baked scene outlives the shell it was baked in. These check the SHAPE of
# the block -- that every question it exists to answer has a slot -- not the
# values, which are properties of whatever machine is running the test.

#: Every key `scene.json` must carry under "provenance", with the sub-keys of
#: the two nested blocks. Written out rather than derived from the code under
#: test, so dropping a field is a test failure rather than a silent agreement.
PROVENANCE_KEYS = {
    "vrgrid": {"commit", "dirty", "source", "note"},
    "patchworkpp": {"requested", "available", "used",
                    "pypatchworkpp_version", "note"},
    "semantic_source": None,
    "semantic_source_param": None,
    "semantic_source_note": None,
    "rerun_sdk": None,
    "rerun_sdk_note": None,
    "rrd": None,
    "python": None,
    "argv": None,
}


def _check_provenance(block, where):
    assert isinstance(block, dict), f"{where}: provenance is not an object"
    for key, nested in PROVENANCE_KEYS.items():
        assert key in block, f"{where}: provenance is missing {key!r}"
        if nested is not None:
            assert isinstance(block[key], dict), f"{where}: {key} is not an object"
            missing = nested - set(block[key])
            assert not missing, f"{where}: provenance.{key} is missing {sorted(missing)}"


def test_provenance_block_has_every_key():
    """The six questions the block exists to answer all have a slot, and the
    facts the caller passes in come back unchanged."""
    argv = ["export_scene.py", "--scene", "ghosts-on", "--rrd"]
    block = P.collect(use_patchworkpp=False, rrd=True, argv=argv)
    _check_provenance(block, "collect()")

    # Run facts are recorded as given, not re-derived.
    assert block["patchworkpp"]["requested"] is False
    assert block["rrd"] is True
    assert block["argv"] == argv


def test_provenance_never_guesses_a_missing_fact():
    """A fact that cannot be established is null WITH a reason, never filled
    in with a plausible value -- an inferred commit would be believed."""
    block = P.collect(use_patchworkpp=True, rrd=False, argv=[])
    # No .rrd was written, so there is no rerun-sdk to report -- and the note
    # has to say which of "absent" and "not asked for" it was.
    assert block["rerun_sdk"] is None
    assert block["rerun_sdk_note"]

    vg = block["vrgrid"]
    assert (vg["commit"] is None) == bool(vg["note"]),         "a missing commit must carry a reason, and a real one must not"
    if vg["commit"] is not None:
        assert len(vg["commit"]) == 40, vg["commit"]
        assert isinstance(vg["dirty"], bool)


def test_manifest_carries_the_provenance_block():
    """The end that matters: what `_write_manifest` actually puts on disk.

    Builds a real `UnrealSink` with no engine and no data -- the manifest is
    written from the schedule and the environment alone, so this needs no
    KITTI on the machine.
    """
    try:
        from vrgrid.grid import schedule as schedule_mod
        from vrgrid_unreal.sink import UnrealSink
    except ImportError as exc:                              # pragma: no cover
        raise AssertionError(
            "the exporter's own dependencies are not importable, so the "
            f"manifest cannot be written on this machine: {exc}"
        ) from exc

    sched = schedule_mod.load("5/10/20/40")
    argv = ["export_scene.py", "--scene", "foveation"]
    with tempfile.TemporaryDirectory() as d:
        sink = UnrealSink(sched, d, engine=None, seq="00", scene="foveation",
                          use_patchworkpp=True, rrd=False, argv=argv)
        sink.finish()
        with open(os.path.join(d, "scene.json"), encoding="utf-8") as f:
            manifest = json.load(f)

    assert "provenance" in manifest, "scene.json has no provenance block"
    _check_provenance(manifest["provenance"], "scene.json")
    assert manifest["provenance"]["argv"] == argv


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
