"""
CFD wrapper for the coupled UrGen v1 backend.
Only handles parameter preparation and dispatching to the physics engine.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import json

from langsmith import traceable

from coupled_UrGen_v1 import main_coupled_run, load_iwec_data
from .artifact_utils import collect_coupled_outputs

DEFAULT_SCENARIO_DATETIME = datetime(1989, 12, 22, 12, 0)


def _default_weather_csv() -> Path:
    """Return the packaged IWEC weather file."""
    return (
        Path(__file__)
        .resolve()
        .parent.parent
        / "coupled_UrGen_v1"
        / "SGP_Singapore_486980_IWEC.csv"
    )


def _resolve_simulation_time(sim_time: Optional[str]) -> datetime:
    """Parse a simulation timestamp; fall back to the reference scenario date."""
    if sim_time:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.fromisoformat(sim_time)
            except ValueError:
                try:
                    return datetime.strptime(sim_time, fmt)
                except ValueError:
                    continue
    return DEFAULT_SCENARIO_DATETIME


@dataclass
class CFDParameters:
    """Parameter pass-through structure for the coupled CFD run."""

    stl_directory: str
    wind_direction_deg: Optional[float] = None
    u_inflow: Optional[float] = None
    z_slice: float = 2.0
    voxel_pitch: float = 4.0
    buffer_ratio: float = 0.10
    T2m_C: Optional[float] = None
    RH2m_percent: Optional[float] = None
    alpha_T: float = 1.5
    alpha_RH: float = 8.0
    building_radius: float = 100.0
    cfd_log_z0: float = 0.5
    simulation_time: Optional[str] = None
    weather_csv_path: Optional[str] = None
    output_dir: Optional[str] = None
    work_dir: Optional[str] = None
    dt_hours: float = 1.0
    vedo_display_mode: str = "off"
    # Optional material/radiation overrides
    rad_albedo_ground: Optional[float] = None
    rad_albedo_wall: Optional[float] = None
    rad_albedo_roof: Optional[float] = None
    rad_emissivity_ground: Optional[float] = None
    rad_emissivity_wall: Optional[float] = None
    rad_emissivity_roof: Optional[float] = None
    rad_thickness_ground: Optional[float] = None
    rad_thickness_wall: Optional[float] = None
    rad_thickness_roof: Optional[float] = None
    rad_C_face_ground: Optional[float] = None
    rad_C_face_wall: Optional[float] = None
    rad_C_face_roof: Optional[float] = None
    rad_k_ground: Optional[float] = None
    rad_k_wall: Optional[float] = None
    rad_k_roof: Optional[float] = None
    rad_rho_ground: Optional[float] = None
    rad_rho_wall: Optional[float] = None
    rad_rho_roof: Optional[float] = None
    rad_cp_ground: Optional[float] = None
    rad_cp_wall: Optional[float] = None
    rad_cp_roof: Optional[float] = None
    be_concrete_k: Optional[float] = None
    be_concrete_l: Optional[float] = None
    be_concrete_rho: Optional[float] = None
    be_concrete_cp: Optional[float] = None


class CFDSolverAgent:
    """Lightweight adapter that forwards parameters to coupled_UrGen_v1."""

    def __init__(self) -> None:
        self.name = "CFD Wrapper (coupled_UrGen_v1)"
        self.description = "Passes CFD parameters to the coupled UrGen solver."

    @traceable(name="CFDSolverAgent.run_analysis")
    def run_analysis(self, params: CFDParameters) -> Dict[str, Any]:
        """Forward the request to the coupled solver without local post-processing."""
        output_dir: Optional[Path] = None
        try:
            stl_dir = Path(params.stl_directory).expanduser().resolve()
            if not stl_dir.is_dir():
                raise FileNotFoundError(f"STL directory not found: {stl_dir}")

            results_root = stl_dir.parent / "results"
            results_root.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = (
                Path(params.output_dir).expanduser().resolve()
                if params.output_dir
                else results_root / f"coupled_cfd_solar_{timestamp}"
            )
            output_dir.mkdir(parents=True, exist_ok=True)

            work_dir = (
                Path(params.work_dir).expanduser().resolve()
                if params.work_dir
                else output_dir / "rt_cache"
            )
            work_dir.mkdir(parents=True, exist_ok=True)

            weather_csv = (
                Path(params.weather_csv_path).expanduser().resolve()
                if params.weather_csv_path
                else _default_weather_csv()
            )

            sim_time = _resolve_simulation_time(params.simulation_time)

            # Preload IWEC time series for logging (single simulation day)
            iwec_timeseries = None
            try:
                iwec_df = load_iwec_data(str(weather_csv), sim_time.year, sim_time.month, sim_time.day)
                # Map columns to a compact schema
                iwec_timeseries = []
                for idx, row in iwec_df.iterrows():
                    iwec_timeseries.append({
                        "datetime": idx.isoformat(),
                        "wind_dir_deg": float(row.get("Wind direction")) if row.get("Wind direction") is not None else None,
                        "wind_speed_ms": float(row.get("Wind Speed")) if row.get("Wind Speed") is not None else None,
                        "air_temp_c": float(row.get("Air Temperature")) if row.get("Air Temperature") is not None else None,
                        "rh_pct": float(row.get("Relative Humidity")) if row.get("Relative Humidity") is not None else None,
                        "dni": float(row.get("Direct Normal Radiation")) if row.get("Direct Normal Radiation") is not None else None,
                        "dhi": float(row.get("Diffuse Horizontal Radiation")) if row.get("Diffuse Horizontal Radiation") is not None else None,
                    })
            except Exception as exc:
                print(f"⚠️ Unable to preload IWEC time series for logging: {exc}")

            print(f"[CFD] Dispatching coupled solver → {output_dir}")
            run_kwargs = {
                "sim_year": sim_time.year,
                "sim_month": sim_time.month,
                "sim_day": sim_time.day,
                "dt_hours": params.dt_hours,
                "common_stl_dir": str(stl_dir),
                "weather_csv_path": str(weather_csv),
                "work_dir": str(work_dir),
                "output_dir": str(output_dir),
                "wind_dir_override": params.wind_direction_deg,
                "wind_speed_override": params.u_inflow,
                "air_temp_override": params.T2m_C,
                "rh_override": params.RH2m_percent,
                "run_cfd": True,
                "run_radiation": True,
                "vedo_display_mode": params.vedo_display_mode,
                "cfd_voxel_pitch": params.voxel_pitch,
                "cfd_buffer_ratio": params.buffer_ratio,
                "cfd_log_z0": params.cfd_log_z0,
            }

            # Attach material overrides only when provided to keep defaults intact.
            material_fields = [
                "rad_albedo_ground",
                "rad_albedo_wall",
                "rad_albedo_roof",
                "rad_emissivity_ground",
                "rad_emissivity_wall",
                "rad_emissivity_roof",
                "rad_thickness_ground",
                "rad_thickness_wall",
                "rad_thickness_roof",
                "rad_C_face_ground",
                "rad_C_face_wall",
                "rad_C_face_roof",
                "rad_k_ground",
                "rad_k_wall",
                "rad_k_roof",
                "rad_rho_ground",
                "rad_rho_wall",
                "rad_rho_roof",
                "rad_cp_ground",
                "rad_cp_wall",
                "rad_cp_roof",
                "be_concrete_k",
                "be_concrete_l",
                "be_concrete_rho",
                "be_concrete_cp",
            ]
            for field_name in material_fields:
                value = getattr(params, field_name, None)
                if value is not None:
                    run_kwargs[field_name] = value

            main_coupled_run(**run_kwargs)

            artifacts = collect_coupled_outputs(output_dir)
            # Write IWEC time series used (if available)
            if iwec_timeseries is not None:
                try:
                    with open(output_dir / "iwec_time_series_used.json", "w", encoding="utf-8") as f:
                        json.dump(iwec_timeseries, f, indent=2, ensure_ascii=False)
                except Exception as exc:
                    print(f"⚠️ Failed to write IWEC time series log: {exc}")
            visualization_files = artifacts["screenshots"] + artifacts["vtk_files"]
            analysis_file = output_dir / "analysis_metrics.json"
            analysis_metrics = None
            if analysis_file.exists():
                try:
                    with open(analysis_file, "r", encoding="utf-8") as f:
                        analysis_metrics = json.load(f)
                except Exception:
                    analysis_metrics = None

            return {
                "success": True,
                "backend": "coupled_UrGen_v1",
                "mode": "cfd",
                "output_directory": str(output_dir),
                "work_directory": str(work_dir),
                "parameters": asdict(params),
                "artifacts": artifacts,
                "visualization_files": visualization_files,
                "data_files": artifacts["data_files"],
                "log_files": artifacts["log_files"],
                "all_files": artifacts["all_files"],
                "analysis_metrics": analysis_metrics,
                "analysis_summary_file": str(analysis_file) if analysis_file.exists() else "",
                "coupled_run": True,
            }

        except Exception as exc:
            print(f"❌ Coupled CFD run failed: {exc}")
            artifacts = collect_coupled_outputs(output_dir) if output_dir else {
                "screenshots": [],
                "vtk_files": [],
                "data_files": [],
                "log_files": [],
                "other_files": [],
                "all_files": [],
            }
            return {
                "success": False,
                "backend": "coupled_UrGen_v1",
                "mode": "cfd",
                "error": str(exc),
                "parameters": asdict(params),
                "artifacts": artifacts,
                "visualization_files": [],
                "data_files": [],
                "log_files": [],
                "all_files": artifacts["all_files"],
                "analysis_metrics": None,
                "analysis_summary_file": str(output_dir / "analysis_metrics.json") if output_dir else "",
            }
