"""
Solar wrapper for the coupled UrGen v1 backend.
Only passes through parameters to the radiation engine.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import json

from langsmith import traceable

from coupled_UrGen_v1 import main_coupled_run

from .artifact_utils import collect_coupled_outputs
from .cfd_solver import _default_weather_csv, _resolve_simulation_time


@dataclass
class SolarParameters:
    """Parameter pass-through structure for radiation runs."""

    stl_directory: str
    time_str: Optional[str] = None
    latitude: float = 1.3521
    longitude: float = 103.8198
    elevation: float = 15.0
    dni_peak: Optional[float] = None
    dhi_peak: Optional[float] = None
    tair_morning_c: float = 25.0
    tair_peak_c: float = 32.0
    tair_peak_hour: float = 14.0
    tair_width_hours: float = 11.0
    rays_per_receiver: int = 64
    batch_size: int = 500_000
    rng_seed: int = 12345
    receiver_offset: float = 0.1
    ground_buffer: float = 20.0
    ground_res: float = 25.0
    z_refine_factor: float = 1.0
    z_refine_max_iters: int = 3
    sky_longwave: Optional[float] = None
    emissivity_ground: float = 0.95
    emissivity_wall: float = 0.92
    emissivity_roof: float = 0.9
    ground_radius: float = 100.0
    shading_threshold: float = 5.0
    interpolate_to_hourly: bool = False
    output_freq: str = "3H"
    dt_hours: float = 1.0
    output_dir: Optional[str] = None
    work_dir: Optional[str] = None
    weather_csv_path: Optional[str] = None
    vedo_display_mode: str = "off"


class SolarSolverAgent:
    """Lightweight adapter that forwards parameters to coupled_UrGen_v1."""

    def __init__(self) -> None:
        self.name = "Solar Wrapper (coupled_UrGen_v1)"
        self.description = "Passes solar parameters to the coupled UrGen solver."

    @traceable(name="SolarSolverAgent.run_analysis")
    def run_analysis(self, params: SolarParameters) -> Dict[str, Any]:
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
                else results_root / f"coupled_solar_{timestamp}"
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

            sim_time = _resolve_simulation_time(params.time_str)

            print(f"[Solar] Dispatching coupled solver → {output_dir}")
            main_coupled_run(
                sim_year=sim_time.year,
                sim_month=sim_time.month,
                sim_day=sim_time.day,
                dt_hours=params.dt_hours,
                common_stl_dir=str(stl_dir),
                weather_csv_path=str(weather_csv),
                work_dir=str(work_dir),
                output_dir=str(output_dir),
                dni_override=params.dni_peak,
                dhi_override=params.dhi_peak,
                sky_lw_override=params.sky_longwave,
                rad_rays_per_receiver=params.rays_per_receiver,
                rad_batch_size=params.batch_size,
                rad_rng_seed=params.rng_seed,
                rad_receiver_offset=params.receiver_offset,
                rad_ground_buffer=params.ground_buffer,
                rad_ground_res=params.ground_res,
                rad_z_refine_factor=params.z_refine_factor,
                rad_z_refine_max_iters=params.z_refine_max_iters,
                rad_emissivity_ground=params.emissivity_ground,
                rad_emissivity_wall=params.emissivity_wall,
                rad_emissivity_roof=params.emissivity_roof,
                rad_lat=params.latitude,
                rad_lon=params.longitude,
                rad_alt=params.elevation,
                run_cfd=True,
                run_radiation=True,
                vedo_display_mode=params.vedo_display_mode,
            )

            artifacts = collect_coupled_outputs(output_dir)
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
                "mode": "solar",
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
            }

        except Exception as exc:
            print(f"❌ Coupled solar run failed: {exc}")
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
                "mode": "solar",
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
