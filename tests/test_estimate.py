"""Tests for /api/estimate (K1) — STL volume + time estimation."""
import pytest
from backend.app.routes_print import _trimesh_stats, estimate_from_stl


@pytest.fixture
def small_stl():
    with open(r"C:\Users\galaz\Desktop\AetAs\model\git2.stl", "rb") as f:
        return f.read()


@pytest.fixture
def cube_stl():
    # 10mm cube = 1 cm³ volume, 1 cm³ → 1g PLA, print ~10mm @ 100mm/s → 0.02s + 0.5h overhead
    # Generate programmatically
    import struct
    faces = []
    # cube vertices (10mm = 1cm)
    v = [[-5,-5,-5],[5,-5,-5],[5,5,-5],[-5,5,-5],[-5,-5,5],[5,-5,5],[5,5,5],[-5,5,5]]
    tris = [[0,1,2],[0,2,3],[4,6,5],[4,7,6],[0,4,5],[0,5,1],[1,5,6],[1,6,2],[2,6,7],[2,7,3],[3,7,4],[3,4,0]]
    header = b"solid cube" + b"\0" * 70
    n = struct.pack("<I", len(tris))
    binary = header + n
    for tri in tris:
        normal = [0,0,1]  # doesn't matter for volume
        binary += struct.pack("<3f", *normal)
        for vi in tri:
            binary += struct.pack("<3f", *v[vi])
        binary += struct.pack("<H", 0)
    return binary


class TestTrimeshStats:
    def test_cube_volume(self, cube_stl):
        """10mm cube should be ~1.0 cm³, not 817 million cm³."""
        r = _trimesh_stats(cube_stl, "PLA")
        assert 0.5 < r["volume_cm3"] < 2.0, f"Expected ~1.0 cm³, got {r['volume_cm3']}"

    def test_cube_dims(self, cube_stl):
        """Cube dimensions should be ~10mm each."""
        r = _trimesh_stats(cube_stl, "PLA")
        assert 9 < r["dimensions_mm"][0] < 11
        assert 9 < r["dimensions_mm"][1] < 11
        assert 9 < r["dimensions_mm"][2] < 11

    def test_cube_grams(self, cube_stl):
        """1 cm³ PLA ≈ 1.24g."""
        r = _trimesh_stats(cube_stl, "PLA")
        assert 0.8 < r["grams"] < 1.6

    def test_real_stl(self, small_stl):
        """Real STL from disk should give sane volume."""
        r = _trimesh_stats(small_stl, "PLA")
        # git2.stl is a real model — volume should be between 1cm³ and 5000 cm³
        assert 1 < r["volume_cm3"] < 5000, f"Got {r['volume_cm3']} — likely parse error"
        assert r["faces"] > 0
