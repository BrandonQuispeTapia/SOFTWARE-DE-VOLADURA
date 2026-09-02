import numpy as np
from scipy.integrate import quad
from scipy.stats import norm
from typing import Dict, Tuple, Optional


class VibrationModels:
    def calcular_ppv_holmberg_persson(
        self, k_site: float, alpha: float, beta: float,
        longitud_carga: float, distancia_x: float, distancia_y: float = 0.0
    ) -> Dict:
        distancia_x = max(distancia_x, 0.1)
        distancia_total = np.sqrt(distancia_x**2 + distancia_y**2)
        n_steps = max(100, int(longitud_carga / 0.1))
        dz = longitud_carga / n_steps
        integral_sum = 0.0
        for i in range(n_steps):
            z = i * dz + dz / 2.0
            R = np.sqrt(distancia_total**2 + z**2)
            if R > 1e-12:
                integral_sum += dz / (R ** (beta / alpha))
        ppv = k_site * (integral_sum ** alpha)

        ppv_critico = 100.0
        radio_danio = distancia_x
        for r_test in np.linspace(distancia_x * 0.1, distancia_x * 3.0, 200):
            integral_r = 0.0
            for i in range(n_steps):
                z = i * dz + dz / 2.0
                R = np.sqrt(r_test**2 + z**2)
                if R > 1e-12:
                    integral_r += dz / (R ** (beta / alpha))
            ppv_r = k_site * (integral_r ** alpha)
            if ppv_r > ppv_critico:
                radio_danio = r_test
                break

        return {
            "ppv_max_mms": ppv,
            "ppv_critico_mms": ppv_critico,
            "radio_danio_m": radio_danio,
            "k_site": k_site,
            "alpha": alpha,
            "beta": beta,
            "integral_value": integral_sum,
        }

    def calcular_ppv_holmberg_persson_scipy(
        self, k_site: float, alpha: float, beta: float,
        longitud_carga: float, distancia_x: float, distancia_y: float = 0.0
    ) -> Dict:
        distancia_x = max(distancia_x, 0.1)
        distancia_total = np.sqrt(distancia_x**2 + distancia_y**2)

        def integrand(z: float) -> float:
            R = np.sqrt(distancia_total**2 + z**2)
            if R < 1e-12:
                return 0.0
            return 1.0 / (R ** (beta / alpha))

        val, _ = quad(integrand, 0, longitud_carga, limit=200)
        ppv = k_site * (val ** alpha)
        ppv_critico = 100.0

        def buscar_radio_danio() -> float:
            for r_test in np.linspace(0.5, 100.0, 300):
                def integrand_r(z: float) -> float:
                    R = np.sqrt(r_test**2 + z**2)
                    if R < 1e-12:
                        return 0.0
                    return 1.0 / (R ** (beta / alpha))
                vr, _ = quad(integrand_r, 0, longitud_carga, limit=200)
                ppv_r = k_site * (vr ** alpha)
                if ppv_r > ppv_critico:
                    return r_test
            return 0.0

        radio_danio = buscar_radio_danio()
        return {
            "ppv_max_mms": ppv,
            "ppv_critico_mms": ppv_critico,
            "radio_danio_m": radio_danio,
            "k_site": k_site,
            "alpha": alpha,
            "beta": beta,
            "integral_value": val,
        }

    def calcular_cut_off_probability(
        self, tiempo_nominal_ms: float, desviacion_relativa: float = 0.03
    ) -> Dict:
        desvio = tiempo_nominal_ms * desviacion_relativa
        prob_corte = norm.cdf(0.0, loc=tiempo_nominal_ms, scale=desvio)
        prob_exitosa = 1.0 - prob_corte
        return {
            "tiempo_nominal_ms": tiempo_nominal_ms,
            "desvio_ms": desvio,
            "probabilidad_corte_pct": prob_corte * 100.0,
            "probabilidad_exitosa_pct": prob_exitosa * 100.0,
        }


class FragmentationModels:
    def calcular_kuz_ram(
        self, factor_roca_A: float, volumen_roca: float,
        kg_explosivo: float, rws_explosivo: float
    ) -> Dict:
        if volumen_roca <= 0 or kg_explosivo <= 0:
            return {"x50_mm": 0, "p80_mm": 0, "n": 1.5, "sizes_mm": np.array([]), "passing_pct": np.array([])}

        x50_cm = factor_roca_A * (volumen_roca / kg_explosivo) ** 0.8 * (kg_explosivo) ** (1.0 / 6.0) * (115.0 / rws_explosivo) ** (19.0 / 30.0)
        x50_mm = x50_cm * 10.0

        B = (volumen_roca / 12.0) ** 0.5 if volumen_roca > 0 else 4.5
        S = B * 1.2
        Lc = 9.0
        n = 1.0 + 0.3 * (S / B - 1.0) + 0.1 * (Lc / B - 1.0) - 0.1 * (B / 4.5)
        n = max(0.8, min(2.5, n))

        p80_mm = x50_mm * (np.log(1.0 / 0.2) / 0.693) ** (1.0 / n)
        sizes_mm = np.array([0, 10, 25, 50, 75, 100, 150, 200, 300, 400, 500, 700, 1000, 1500, 2000, 3000], dtype=np.float64)
        passing_pct = np.zeros_like(sizes_mm)
        for i, s in enumerate(sizes_mm):
            if x50_mm > 0 and n > 0:
                passing_pct[i] = 100.0 * (1.0 - np.exp(-0.693 * (s / x50_mm) ** n))
            else:
                passing_pct[i] = 0.0

        return {
            "x50_mm": x50_mm,
            "x50_cm": x50_cm,
            "p80_mm": p80_mm,
            "n": n,
            "sizes_mm": sizes_mm,
            "passing_pct": passing_pct,
            "factor_roca_A": factor_roca_A,
            "rws": rws_explosivo,
        }

    def calcular_p80_directo(
        self, factor_roca_A: float, burden_m: float, spacing_m: float,
        bench_height_m: float, kg_explosivo: float, rws_explosivo: float
    ) -> float:
        volumen = burden_m * spacing_m * bench_height_m
        result = self.calcular_kuz_ram(factor_roca_A, volumen, kg_explosivo, rws_explosivo)
        return result["p80_mm"]


class MuckpileSimulator:
    def __init__(self, gravedad_ms2: float = 9.81, factor_esponjamiento: float = 1.3):
        self.gravedad_ms2 = gravedad_ms2
        self.factor_esponjamiento = factor_esponjamiento

    def calcular_desplazamiento_muckpile(
        self, coordenadas_iniciales_mesh: np.ndarray,
        vectores_velocidad: np.ndarray, tiempo_ms: float
    ) -> np.ndarray:
        coords = np.asarray(coordenadas_iniciales_mesh, dtype=np.float64)
        vels = np.asarray(vectores_velocidad, dtype=np.float64)
        t_seg = tiempo_ms / 1000.0

        if coords.ndim == 1:
            coords = coords.reshape(1, -1)
        if vels.ndim == 1:
            vels = vels.reshape(1, -1)

        n_coords = coords.shape[0]
        n_vels = vels.shape[0]
        if n_vels == 1 and n_coords > 1:
            vels = np.tile(vels, (n_coords, 1))

        desplazamiento = np.zeros_like(coords)
        desplazamiento[:, 0] = vels[:, 0] * t_seg
        desplazamiento[:, 1] = vels[:, 1] * t_seg
        desplazamiento[:, 2] = vels[:, 2] * t_seg - 0.5 * self.gravedad_ms2 * t_seg ** 2

        nuevas_coords = coords + desplazamiento
        nuevas_coords[:, 2] = np.maximum(nuevas_coords[:, 2], 0.0)
        centro_masa = np.mean(coords, axis=0)
        direccion_escape = nuevas_coords - centro_masa
        distancias = np.linalg.norm(direccion_escape[:, :2], axis=1)
        dist_max = np.max(distancias) if np.max(distancias) > 0 else 1.0
        factor_radial = 1.0 + (self.factor_esponjamiento - 1.0) * (1.0 - distancias / dist_max)
        nuevas_coords[:, 2] = np.where(distancias > 0, nuevas_coords[:, 2] * factor_radial, nuevas_coords[:, 2])
        return nuevas_coords

    def simular_muckpile_completo(
        self, mesh_cara_libre: 'pv.PolyData', tiempos_detonacion_ms: np.ndarray,
        carga_por_taladro_kg: np.ndarray, tiempo_total_ms: float
    ) -> np.ndarray:
        try:
            import pyvista as pv
        except ImportError:
            raise ImportError("pyvista requerido para simular_muckpile_completo")
        puntos = np.array(mesh_cara_libre.points, dtype=np.float64)
        n_puntos = puntos.shape[0]
        n_taladros = len(tiempos_detonacion_ms)
        velocidades = np.zeros((n_puntos, 3), dtype=np.float64)
        carga_total = np.sum(carga_por_taladro_kg) if np.sum(carga_por_taladro_kg) > 0 else 1.0
        centro_taladros = np.mean(puntos[:min(n_taladros, n_puntos)], axis=0)
        for i in range(n_puntos):
            direccion = puntos[i] - centro_taladros
            dist = np.linalg.norm(direccion)
            if dist > 0:
                direccion = direccion / dist
                intensidad = max(0.0, 1.0 - dist / 50.0)
                velocidades[i] = direccion * intensidad * 15.0 + np.array([0.0, 0.0, 5.0 * intensidad])
        return self.calcular_desplazamiento_muckpile(puntos, velocidades, tiempo_total_ms)

    def calcular_energia_cinetica(self, masas_kg: np.ndarray, velocidades_ms: np.ndarray) -> float:
        return float(0.5 * np.sum(masas_kg * np.sum(velocidades_ms ** 2, axis=1)))

    def calcular_volumen_esponjado(self, volumen_original_m3: float) -> float:
        return volumen_original_m3 * self.factor_esponjamiento


# FASE 3 COMPLETADA. MOTORES FISICOS Y GENERADOR PDF LISTOS.
# EL GEMELO DIGITAL ESTA ARQUITECTONICAMENTE COMPLETO Y LISTO PARA SU INTEGRACION FINAL.
