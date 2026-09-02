"""
test_phase1.py — Verificación de la Fase 1: Core Domain & Physics
=================================================================
Ejecuta validaciones trigonométricas, de masa explosiva y reportes.
"""
import sys, math
sys.path.insert(0, ".")

from core.geometry import Point3D, Vector3D, Drillhole, BlastPattern, PatternType
from core.rock_mass import RockProperties, MWDRecord, DrillholeMWD, ROCK_CATALOG
from core.explosives import Explosive, EXPLOSIVE_CATALOG, ExplosiveDeck
from reports.report_generator import PDFReportBuilder
from pathlib import Path

PASS = 0
FAIL = 0

def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} — {detail}")

print("=" * 65)
print("  VOLADURA_PRO_10X — Test Fase 1")
print("=" * 65)

# ── 1. Geometría 3D ─────────────────────────────────────────────
print("\n▸ GEOMETRÍA 3D")

p1 = Point3D(0, 0, 100)
p2 = Point3D(3, 4, 100)
check("Point3D distance", abs(p1.distance_to(p2) - 5.0) < 1e-9, f"got {p1.distance_to(p2)}")

v = Vector3D(3, 4, 0)
check("Vector3D magnitude", abs(v.magnitude - 5.0) < 1e-9)

vn = v.normalize()
check("Vector3D normalize", abs(vn.magnitude - 1.0) < 1e-9)

# Taladro vertical (dip=0°): toe debe estar directamente debajo
h_vert = Drillhole(
    hole_id="V-001", collar=Point3D(100, 200, 4000),
    diameter_mm=165.0, length=13.0, azimuth_deg=0.0, dip_deg=0.0,
)
toe = h_vert.toe
check("Vertical drillhole toe.z", abs(toe.z - (4000 - 13.0)) < 1e-6,
      f"expected 3987, got {toe.z:.4f}")
check("Vertical drillhole toe.x", abs(toe.x - 100) < 1e-6)

# Taladro inclinado 10° desde vertical, azimuth 0° (Norte)
h_inc = Drillhole(
    hole_id="I-001", collar=Point3D(0, 0, 100),
    diameter_mm=165.0, length=15.0, azimuth_deg=0.0, dip_deg=10.0,
)
toe_inc = h_inc.toe
expected_dz = -15.0 * math.cos(math.radians(10))
expected_dy = 15.0 * math.sin(math.radians(10)) * math.cos(0)
check("Inclined toe dZ", abs(toe_inc.z - (100 + expected_dz)) < 1e-4,
      f"expected {100 + expected_dz:.4f}, got {toe_inc.z:.4f}")
check("Inclined toe dY", abs(toe_inc.y - expected_dy) < 1e-4,
      f"expected {expected_dy:.4f}, got {toe_inc.y:.4f}")

# Volumen cilíndrico
vol = h_vert.calculate_volume()
expected_vol = math.pi * (0.165 / 2) ** 2 * 13.0
check("Drillhole volume", abs(vol - expected_vol) < 1e-6,
      f"expected {expected_vol:.6f}, got {vol:.6f}")

# ── 2. BlastPattern ─────────────────────────────────────────────
print("\n▸ BLAST PATTERN")

burden = BlastPattern.konya_burden(165.0, 0.85, 2.6)
check("Konya burden > 0", burden > 0, f"got {burden}")
check("Konya burden ~3.4m", 3.0 < burden < 4.5, f"got {burden}")

spacing = BlastPattern.ash_spacing(burden, 1.25)
check("Ash spacing = 1.25*B", abs(spacing - burden * 1.25) < 1e-3)

pattern = BlastPattern(
    pattern_id="TEST-001",
    origin=Point3D(0, 0, 4000),
    burden=burden, spacing=spacing,
    bench_height=10.0, subdrill=0.8, stemming=2.5,
    num_rows=3, holes_per_row=5,
    pattern_type=PatternType.RECTANGULAR,
)
pattern.generate_grid(diameter_mm=165.0)
check("Grid generation count", pattern.total_holes == 15, f"got {pattern.total_holes}")
check("Collar matrix shape", pattern.get_collar_matrix().shape == (15, 3))

# ── 3. Explosivos ───────────────────────────────────────────────
print("\n▸ EXPLOSIVOS")

anfo = EXPLOSIVE_CATALOG["anfo"]
check("ANFO density", abs(anfo.density_gcc - 0.85) < 1e-6)
check("ANFO VOD", anfo.vod_ms == 4500.0)

mass = anfo.cylindrical_charge_mass(0.165, 7.0)
expected_mass = math.pi * (0.165 / 2) ** 2 * 7.0 * 850.0
check("ANFO charge mass", abs(mass - expected_mass) < 0.1,
      f"expected {expected_mass:.2f}kg, got {mass:.2f}kg")

# Desacoplamiento
mass_dc = anfo.cylindrical_charge_mass(0.165, 7.0, decoupling_ratio=0.8)
check("Decoupled mass < coupled", mass_dc < mass,
      f"dc={mass_dc:.2f} vs coupled={mass:.2f}")

# Presión borehole Chapman-Jouguet
pbh = anfo.peak_borehole_pressure_mpa()
check("Borehole pressure > 1000 MPa", pbh > 1000,
      f"P_CJ = {pbh:.0f} MPa")

# Load explosives en drillhole
h_vert.load_explosives(
    {"name": "ANFO", "density_gcc": 0.85}, top_stemming=2.5
)
check("Drillhole total_charge > 0", h_vert.total_charge_kg > 0,
      f"got {h_vert.total_charge_kg:.2f}kg")

# ── 4. Geomecánica ──────────────────────────────────────────────
print("\n▸ GEOMECÁNICA (Rock Mass)")

granite = ROCK_CATALOG["hard"]
check("Granite density", abs(granite.density_tm3 - 2.7) < 1e-6)
check("Granite RMR > 0", granite.rmr89 > 0, f"RMR = {granite.rmr89:.1f}")
check("Granite GSI = RMR-5", abs(granite.gsi - (granite.rmr89 - 5)) < 1e-6)
check("Rock class", granite.rock_class.value in ["I", "II", "III", "IV", "V"])
check("Rock catalog has 5 types", len(ROCK_CATALOG) == 5)

# MWD Profile
mwd = DrillholeMWD(hole_id="V-001", total_length_m=13.0)
mwd.add_record(MWDRecord(0.0, 3.0, penetration_rate_mmin=1.5, feed_pressure_bar=100))
mwd.add_record(MWDRecord(3.0, 8.0, penetration_rate_mmin=0.8, feed_pressure_bar=150))
mwd.add_record(MWDRecord(8.0, 13.0, penetration_rate_mmin=0.5, feed_pressure_bar=200))
check("MWD 3 records", len(mwd.records) == 3)
check("MWD avg PR > 0", mwd.average_penetration_rate > 0)
check("MWD avg UCS > 0", mwd.average_ucs_mpa > 0)
check("MWD hard zones", len(mwd.get_hard_zones(100.0)) >= 0)

profile = mwd.hardness_profile
check("MWD hardness profile len=3", len(profile) == 3)

ucs_at_5 = mwd.ucs_at_depth(5.0)
check("MWD UCS at 5m depth", ucs_at_5 is not None and ucs_at_5 > 0)

# ── 5. Report Generator ─────────────────────────────────────────
print("\n▸ REPORT GENERATOR")

try:
    gen = PDFReportBuilder(
        output_dir=Path("./test_reports"),
        company_name="Minera Test S.A.",
        project_name="Banco Norte",
        responsable="Ing. Test",
        cargo="Jefe P&V",
    )
    check("PDFReportBuilder init", True)

    path = gen.build_executive_report(
        pattern=pattern, 
        rock=granite
    )
    check(f"PDF/HTML output exists", path.exists(), f"path={path}")

except Exception as e:
    check(f"PDFReportBuilder", False, str(e))

# ── Resumen ──────────────────────────────────────────────────────
print("\n" + "=" * 65)
print(f"  RESULTADOS: {PASS} passed, {FAIL} failed, {PASS + FAIL} total")
if FAIL == 0:
    print("  🎯 FASE 1 COMPLETADA — Todos los tests pasaron.")
else:
    print(f"  ⚠️  {FAIL} test(s) fallaron.")
print("=" * 65)
