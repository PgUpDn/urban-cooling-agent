"""
Complete Building Analysis with LLM Interaction Recording
Generates visualizations and records all GPT-5 interactions
"""
import json
import os
import sys
import time
import argparse
import copy
from datetime import datetime
from pathlib import Path
from intelligent_building_agent import IntelligentBuildingAgent
from config import OPENAI_API_KEY


class LLMInteractionRecorder:
    """Records all LLM interactions"""
    
    def __init__(self, output_dir="/scratch/Urban/intelligent_agent_package/results"):
        self.output_dir = output_dir
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.interactions = []
        self.log_file = f"{output_dir}/llm_interactions_{self.timestamp}.json"
        self.summary_file = f"{output_dir}/analysis_summary_{self.timestamp}.txt"
        
    def record_interaction(self, stage, prompt, response, elapsed_time):
        """Record one LLM interaction"""
        interaction = {
            'timestamp': datetime.now().isoformat(),
            'stage': stage,
            'prompt': prompt,
            'response': response,
            'elapsed_time': elapsed_time,
            'prompt_length': len(prompt),
            'response_length': len(response)
        }
        self.interactions.append(interaction)
        
        # Save in real-time
        self.save_interactions()
        
        # Print to console
        print(f"\n{'='*80}")
        print(f"🤖 LLM Interaction Record - {stage}")
        print(f"{'='*80}")
        print(f"📝 Prompt ({len(prompt)} chars):")
        print(f"{prompt[:200]}..." if len(prompt) > 200 else prompt)
        print(f"\n💬 Response ({len(response)} chars):")
        print(f"{response[:300]}..." if len(response) > 300 else response)
        print(f"\n⏱️  Duration: {elapsed_time:.2f}s")
        print(f"{'='*80}\n")
    
    def save_interactions(self):
        """Save all interactions to file"""
        data = {
            'session_info': {
                'timestamp': self.timestamp,
                'total_interactions': len(self.interactions),
                'total_time': sum(i['elapsed_time'] for i in self.interactions)
            },
            'interactions': self.interactions
        }
        
        with open(self.log_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def save_summary(self, analysis_result, user_query=""):
        """Save analysis summary"""
        with open(self.summary_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("Building Analysis Summary\n")
            f.write("="*80 + "\n\n")
            
            # Handle None analysis_result
            if analysis_result is None:
                f.write("Status: ❌ Analysis Failed (returned None)\n\n")
                if user_query:
                    f.write("User Query:\n")
                    f.write("-" * 40 + "\n")
                    f.write(f"{user_query}\n\n")
                f.write("\nError: Analysis returned None. Check logs for details.\n")
                return
            
            f.write(f"Timestamp: {self.timestamp}\n")
            f.write(f"Success: {analysis_result.get('success', False)}\n\n")
            
            # User Query
            if user_query:
                f.write("User Query:\n")
                f.write("-" * 40 + "\n")
                f.write(f"{user_query}\n\n")
            
            # LLM interaction statistics
            f.write("LLM Interaction Statistics:\n")
            f.write("-" * 40 + "\n")
            f.write(f"Total interactions: {len(self.interactions)}\n")
            total_time = sum(i['elapsed_time'] for i in self.interactions)
            f.write(f"Total LLM time: {total_time:.2f}s\n")
            f.write(f"Average time: {total_time/len(self.interactions):.2f}s\n")
            total_prompt_chars = sum(i['prompt_length'] for i in self.interactions)
            total_response_chars = sum(i['response_length'] for i in self.interactions)
            f.write(f"Total prompt chars: {total_prompt_chars:,}\n")
            f.write(f"Total response chars: {total_response_chars:,}\n\n")
            
            # Solver results
            if 'solver_results' in analysis_result and analysis_result['solver_results'] is not None:
                f.write("\nSolver Results:\n")
                f.write("-" * 40 + "\n")
                for solver, result in analysis_result['solver_results'].items():
                    f.write(f"\n{solver.upper()}:\n")
                    if result.get('success'):
                        f.write(f"  ✅ Success\n")
                        if 'output_file' in result:
                            f.write(f"  📄 Data: {result['output_file']}\n")
                        if 'visualization_file' in result:
                            f.write(f"  🎨 Visualization: {result['visualization_file']}\n")
                    else:
                        f.write(f"  ❌ Failed: {result.get('error', 'Unknown')}\n")
            
            # Output files
            if 'output_files' in analysis_result:
                files = analysis_result['output_files']
                f.write("\n\nOutput Files:\n")
                f.write("-" * 40 + "\n")
                for csv in files.get('csv_files', []):
                    f.write(f"📊 {csv['solver']}: {csv['file']}\n")
                for viz in files.get('visualization_files', []):
                    f.write(f"🎨 {viz['solver']}: {viz['file']}\n")
            
            # Agent response
            f.write("\n\nAgent Response:\n")
            f.write("-" * 40 + "\n")
            f.write(analysis_result.get('response', 'No response'))
            
        print(f"\n📝 Summary saved to: {self.summary_file}")


class InstrumentedAgent(IntelligentBuildingAgent):
    """Agent with LLM interaction recording (legacy shim)."""

    def __init__(self, api_key, recorder=None, config_file=None, allow_llm_params=True):
        super().__init__(api_key, config_file=config_file, allow_llm_params=allow_llm_params)
        self.recorder = recorder

    def _analyze_intent(self, state):
        return super()._analyze_intent(state)


DEFAULT_MATERIAL_BASELINE = {
    "albedo_roof": 0.6,
    "albedo_wall": 0.4,
    "albedo_ground": 0.2,
    "emissivity_roof": 0.9,
    "emissivity_wall": 0.92,
    "emissivity_ground": 0.95,
    "thickness_roof": 0.15,
    "thickness_wall": 0.2,
    "thickness_ground": 0.5,
    "c_face_roof": 0.5e6,
    "c_face_wall": 0.5e6,
    "c_face_ground": 0.5e6,
    "k_roof": None,
    "k_wall": None,
    "k_ground": None,
    "rho_roof": None,
    "rho_wall": None,
    "rho_ground": None,
    "cp_roof": None,
    "cp_wall": None,
    "cp_ground": None,
    "k_concrete": 1.7,
    "rho_concrete": 2200,
    "cp_concrete": 880,
    "thickness_concrete": 0.2,
}


def _extract_materials_from_params(params: dict) -> dict:
    """Normalize material fields from CFD parameters with sensible defaults."""
    mapping = {
        "albedo_roof": "rad_albedo_roof",
        "albedo_wall": "rad_albedo_wall",
        "albedo_ground": "rad_albedo_ground",
        "emissivity_roof": "rad_emissivity_roof",
        "emissivity_wall": "rad_emissivity_wall",
        "emissivity_ground": "rad_emissivity_ground",
        "thickness_roof": "rad_thickness_roof",
        "thickness_wall": "rad_thickness_wall",
        "thickness_ground": "rad_thickness_ground",
        "c_face_roof": "rad_C_face_roof",
        "c_face_wall": "rad_C_face_wall",
        "c_face_ground": "rad_C_face_ground",
        "k_roof": "rad_k_roof",
        "k_wall": "rad_k_wall",
        "k_ground": "rad_k_ground",
        "rho_roof": "rad_rho_roof",
        "rho_wall": "rad_rho_wall",
        "rho_ground": "rad_rho_ground",
        "cp_roof": "rad_cp_roof",
        "cp_wall": "rad_cp_wall",
        "cp_ground": "rad_cp_ground",
        "k_concrete": "be_concrete_k",
        "rho_concrete": "be_concrete_rho",
        "cp_concrete": "be_concrete_cp",
        "thickness_concrete": "be_concrete_l",
    }
    normalized = {}
    for short, long_key in mapping.items():
        val = params.get(long_key)
        normalized[short] = val if val is not None else DEFAULT_MATERIAL_BASELINE[short]
    return normalized


def _load_analysis_metrics_from_result(cfd_result: dict) -> dict:
    """Load analysis_metrics.json if available, falling back to embedded metrics."""
    metrics = cfd_result.get("analysis_metrics")
    if metrics:
        return metrics
    metrics_path = cfd_result.get("analysis_summary_file") or cfd_result.get("analysis_metrics_file")
    if metrics_path and os.path.exists(metrics_path):
        try:
            with open(metrics_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _material_targets_from_metrics(metrics: dict) -> list:
    targets = set()
    cooling = (metrics or {}).get("cooling_energy", {})
    per_building = cooling.get("per_building_kWh", {}) or {}
    if per_building:
        top3 = sorted(per_building.items(), key=lambda kv: kv[1], reverse=True)[:3]
        targets.update([k for k, _ in top3])
    hotspots = (metrics or {}).get("ground_hotspots") or []
    for h in hotspots:
        for b in h.get("nearest_buildings", []):
            targets.add(b)
    return sorted(targets)


def _propose_material_overrides(metrics: dict, baseline_materials: dict) -> dict:
    """Heuristic: raise albedo on roofs/walls/ground and emissivity on roofs/walls."""
    reco = dict(baseline_materials)
    # Boost reflectance to cut gains and surface temps.
    reco["albedo_roof"] = max(baseline_materials.get("albedo_roof", 0.6), 0.72)
    reco["albedo_wall"] = max(baseline_materials.get("albedo_wall", 0.4), 0.55)
    reco["albedo_ground"] = max(baseline_materials.get("albedo_ground", 0.2), 0.25)
    # Keep emissivity high to enhance longwave release.
    reco["emissivity_roof"] = max(baseline_materials.get("emissivity_roof", 0.9), 0.93)
    reco["emissivity_wall"] = max(baseline_materials.get("emissivity_wall", 0.92), 0.94)
    # Leave thickness / C_face unchanged by default; user can extend later.
    targets = _material_targets_from_metrics(metrics)
    rationale = [
        "Increase roof albedo toward cool-roof range to reduce solar heat gains and roof MRT.",
        "Lighten walls to cut façade solar absorption and lower cooling load.",
        "Slightly lighten ground to ease MRT in pedestrian zones without over-brightening.",
        "Maintain high emissivity so surfaces re-radiate efficiently after peak sun.",
        "Target buildings are derived from highest cooling load and PET/MRT hotspots.",
    ]
    material_selection = {
        "roof": {
            "name": "Cool roof (white membrane / coated metal)",
            "albedo": reco["albedo_roof"],
            "emissivity": reco["emissivity_roof"],
        },
        "wall": {
            "name": "Light façade (light stucco or reflective glass mix)",
            "albedo": reco["albedo_wall"],
            "emissivity": reco["emissivity_wall"],
        },
        "ground": {
            "name": "Light concrete / pavers",
            "albedo": reco["albedo_ground"],
            "emissivity": reco.get("emissivity_ground", baseline_materials.get("emissivity_ground")),
        },
    }
    return {
        "materials": reco,
        "targets": targets,
        "rationale": rationale,
        "material_selection": material_selection,
    }


def _compare_material_runs(base_metrics: dict, tuned_metrics: dict, base_materials: dict, tuned_materials: dict) -> dict:
    cooling_base = ((base_metrics or {}).get("cooling_energy") or {}).get("total_kWh")
    cooling_tuned = ((tuned_metrics or {}).get("cooling_energy") or {}).get("total_kWh")
    per_building_base = ((base_metrics or {}).get("cooling_energy") or {}).get("per_building_kWh") or {}
    per_building_tuned = ((tuned_metrics or {}).get("cooling_energy") or {}).get("per_building_kWh") or {}
    per_building_peak_base = ((base_metrics or {}).get("cooling_energy") or {}).get("per_building_max_hourly_kw") or {}
    per_building_peak_tuned = ((tuned_metrics or {}).get("cooling_energy") or {}).get("per_building_max_hourly_kw") or {}

    def _delta_pct(a, b):
        if a is None or b is None:
            return None
        if a == 0:
            return None
        return round(100.0 * (b - a) / a, 2)

    def _max_pet(metrics: dict):
        hotspots = (metrics or {}).get("ground_hotspots") or []
        if not hotspots:
            return None
        try:
            return max(h.get("pet_c") for h in hotspots if h.get("pet_c") is not None)
        except Exception:
            return None

    def _normalize_peak_kw(entry):
        """Extract a numeric peak kW value from either a raw number or {'value': x} dict."""
        if entry is None:
            return None
        if isinstance(entry, (int, float)):
            return entry
        if isinstance(entry, dict):
            val = entry.get("value")
            return val if isinstance(val, (int, float)) else None
        return None

    def _per_building_delta(before: dict, after: dict):
        out = {}
        keys = set(before.keys()) | set(after.keys())
        for k in keys:
            a_raw = before.get(k)
            b_raw = after.get(k)
            a = _normalize_peak_kw(a_raw)
            b = _normalize_peak_kw(b_raw)
            if a is None and b is None:
                continue
            delta = None if (a is None or b is None) else round(b - a, 6)
            pct = _delta_pct(a, b)
            out[k] = {
                "before": a,
                "after": b,
                "delta": delta,
                "pct_change": pct,
            }
        return out

    return {
        "cooling_kWh_before": cooling_base,
        "cooling_kWh_after": cooling_tuned,
        "cooling_kWh_delta": None if (cooling_base is None or cooling_tuned is None) else round(cooling_tuned - cooling_base, 3),
        "cooling_pct_change": _delta_pct(cooling_base, cooling_tuned),
        "max_pet_before": _max_pet(base_metrics),
        "max_pet_after": _max_pet(tuned_metrics),
        "materials_before": base_materials,
        "materials_after": tuned_materials,
        "per_building_kWh_delta": _per_building_delta(per_building_base, per_building_tuned),
        "per_building_peak_kw_delta": _per_building_delta(per_building_peak_base, per_building_peak_tuned),
    }


class StdoutFileLogger:
    """Context manager that mirrors stdout to a file (tee)."""

    def __init__(self, log_path: Path, mode: str = "w"):
        self.log_path = Path(log_path)
        self.mode = mode
        self.original_stdout = None
        self.log_file = None

    def __enter__(self):
        self.original_stdout = sys.stdout
        self.log_file = open(self.log_path, self.mode, encoding="utf-8")
        sys.stdout = self
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.log_file:
            self.log_file.close()
        sys.stdout = self.original_stdout

    def write(self, data):
        if self.original_stdout:
            self.original_stdout.write(data)
        if self.log_file:
            self.log_file.write(data)
            self.log_file.flush()

    def flush(self):
        if self.original_stdout:
            self.original_stdout.flush()
        if self.log_file:
            self.log_file.flush()


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Complete Building Analysis with LLM Interaction Recording",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings (LLM can suggest parameters)
  python full_analysis_with_recording_en.py
  
  # Disable LLM parameter modification (use only JSON config + user params)
  python full_analysis_with_recording_en.py --no-llm-params
  
  # Use custom config file
  python full_analysis_with_recording_en.py --config my_config.json
  
  # Disable LLM params and use custom config
  python full_analysis_with_recording_en.py --no-llm-params --config my_config.json
        """
    )
    
    parser.add_argument(
        '--no-llm-params',
        dest='allow_llm_params',
        action='store_false',
        default=True,
        help='Disable LLM parameter suggestions (use only JSON config + user parameters)'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default='/scratch/Urban/intelligent_agent_package/solver_parameters.json',
        help='Path to JSON configuration file (default: solver_parameters.json)'
    )
    parser.add_argument(
        '--stl-directory',
        type=str,
        default='/scratch/Urban/intelligent_agent_package/example_stl/town_00001_500_1.379_103.893_14553_1532',
        help='Path to directory containing STL files (default: example_stl/town_00001_500_1.379_103.893_14553_1532)'
    )
    
    parser.add_argument(
        '--tests',
        nargs='+',
        choices=['1', '2', '3', '4', '5', '5m', 'material', 'mat', 'matopt', 'coupled', 'all'],
        default=['all'],
        help='Specify which seasonal/coupled tests to run (numbers, "coupled", or "all").'
    )
    parser.add_argument(
        '--material-tuning',
        dest='material_tuning',
        action='store_true',
        default=False,
        help='Enable material tuning auto-loop: replace Test 5 with 5m (baseline + tuned rerun).'
    )
    
    return parser.parse_args()


def run_material_tuning_test(agent, test, stl_directory, test_output_dir):
    """Run baseline Test 5, propose material tweaks, rerun, and compare."""
    os.makedirs(test_output_dir, exist_ok=True)
    baseline_dir = os.path.join(test_output_dir, "baseline")
    tuned_dir = os.path.join(test_output_dir, "material_tuned")

    start_time = time.time()
    print("\n🧪 Material tuning pipeline: baseline pass")
    baseline_result = agent.analyze(
        query=test["query"],
        stl_directory=stl_directory,
        user_parameters=test.get("params"),
        output_directory=baseline_dir
    )
    # Save baseline summary
    try:
        baseline_recorder = LLMInteractionRecorder(output_dir=baseline_dir)
        baseline_recorder.interactions = agent.get_llm_interactions()
        baseline_recorder.save_summary(baseline_result, user_query=test["query"])
    except Exception as exc:
        print(f"⚠️ Failed to write baseline summary: {exc}")
    baseline_cfd = (baseline_result.get("solver_results") or {}).get("cfd", {}) if baseline_result else {}
    baseline_metrics = _load_analysis_metrics_from_result(baseline_cfd)
    baseline_materials = _extract_materials_from_params(baseline_cfd.get("parameters", {})) if baseline_cfd else DEFAULT_MATERIAL_BASELINE

    proposal = _propose_material_overrides(baseline_metrics, baseline_materials)
    plan = {
        "baseline_output": baseline_dir,
        "baseline_materials": baseline_materials,
        "proposed_materials": proposal.get("materials", {}),
        "material_selection": proposal.get("material_selection", {}),
        "targets": proposal.get("targets", []),
        "rationale": proposal.get("rationale", []),
        "material_properties_reference": "coupled_UrGen_v1/material_properties.md",
    }
    plan_path = os.path.join(test_output_dir, "material_tuning_plan.json")
    try:
        with open(plan_path, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        print(f"⚠️ Failed to write material tuning plan: {exc}")

    tuned_params = copy.deepcopy(test.get("params", {}))
    tuned_params["materials"] = proposal.get("materials", {})
    tuned_params["reuse_geometry_from"] = baseline_dir
    tuned_params["comparison"] = {
        "baseline_dir": baseline_dir,
        "baseline_metrics": baseline_metrics,
        "baseline_materials": baseline_materials,
        "baseline_metrics_path": os.path.join(baseline_dir, "cfd_solar", "analysis_metrics.json"),
        "baseline_cfd_parameters_path": os.path.join(baseline_dir, "final_cfd_parameters.json"),
        "comparison_file": os.path.join(test_output_dir, "material_tuning_comparison.json"),
        "plan_file": plan_path,
    }
    tuned_query = test.get("tuned_query") or (test["query"] + " (material tuning pass)")
    # Reuse baseline radiation cache to avoid duplicate heavy geometry/ray work
    cfd_params = tuned_params.setdefault("cfd", {})
    cfd_params.setdefault("work_dir", os.path.join(baseline_dir, "cfd_solar", "rt_cache"))

    print("\n🧪 Material tuning pipeline: tuned pass")
    tuned_result = agent.analyze(
        query=tuned_query,
        stl_directory=stl_directory,
        user_parameters=tuned_params,
        output_directory=tuned_dir
    )
    # Save tuned summary
    try:
        tuned_recorder = LLMInteractionRecorder(output_dir=tuned_dir)
        tuned_recorder.interactions = agent.get_llm_interactions()
        tuned_recorder.save_summary(tuned_result, user_query=tuned_query)
    except Exception as exc:
        print(f"⚠️ Failed to write tuned summary: {exc}")
    tuned_cfd = (tuned_result.get("solver_results") or {}).get("cfd", {}) if tuned_result else {}
    tuned_metrics = _load_analysis_metrics_from_result(tuned_cfd)
    tuned_materials = _extract_materials_from_params(tuned_cfd.get("parameters", {})) if tuned_cfd else DEFAULT_MATERIAL_BASELINE

    comparison = _compare_material_runs(baseline_metrics, tuned_metrics, baseline_materials, tuned_materials)
    comparison_path = os.path.join(test_output_dir, "material_tuning_comparison.json")
    try:
        with open(comparison_path, "w", encoding="utf-8") as f:
            json.dump(comparison, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        print(f"⚠️ Failed to write material tuning comparison: {exc}")

    # Write a brief human-readable diff with cooling deltas
    diff_txt = os.path.join(test_output_dir, "material_tuning_diff.txt")
    try:
        lines = []
        lines.append("Material Tuning Quantitative Diff")
        lines.append("=================================")
        lines.append(f"Baseline metrics: {baseline_dir}")
        lines.append(f"Tuned metrics:    {tuned_dir}")
        lines.append(f"Comparison JSON:  {comparison_path}")
        lines.append("")
        lines.append("Cooling load (total kWh):")
        lines.append(f"  Before: {comparison.get('cooling_kWh_before')}")
        lines.append(f"  After:  {comparison.get('cooling_kWh_after')}")
        lines.append(f"  Delta:  {comparison.get('cooling_kWh_delta')} kWh "
                     f"({comparison.get('cooling_pct_change')} %)")
        lines.append("")

        # Top 5 absolute kWh increases/decreases per building
        per_bld = comparison.get("per_building_kWh_delta") or {}
        deltas = []
        for bid, rec in per_bld.items():
            delta = rec.get("delta")
            if delta is None:
                continue
            deltas.append((bid, delta, rec.get("before"), rec.get("after"), rec.get("pct_change")))
        deltas_sorted = sorted(deltas, key=lambda x: abs(x[1]), reverse=True)
        lines.append("Top 5 |ΔkWh| per building:")
        for bid, delta, before, after, pct in deltas_sorted[:5]:
            lines.append(f"  {bid}: before={before}, after={after}, delta={delta}, pct={pct}%")

        lines.append("")
        lines.append("Max PET (ground hotspots):")
        lines.append(f"  Before: {comparison.get('max_pet_before')}")
        lines.append(f"  After:  {comparison.get('max_pet_after')}")

        with open(diff_txt, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception as exc:
        print(f"⚠️ Failed to write material tuning diff text: {exc}")

    total_time = time.time() - start_time
    success = bool(baseline_result and baseline_result.get("success") and tuned_result and tuned_result.get("success"))

    # Write a lightweight overall summary pointer
    summary_txt = os.path.join(test_output_dir, "analysis_summary_material_tuning.txt")
    try:
        lines = [
            "Material Tuning Summary",
            "=======================",
            f"Baseline dir: {baseline_dir}",
            f"Tuned dir:    {tuned_dir}",
            f"Plan file:    {plan_path}",
            f"Comparison:   {comparison_path}",
            f"Diff (text):  {diff_txt}",
            "",
            f"Success: {success}",
            f"Elapsed: {total_time:.1f} s",
        ]
        with open(summary_txt, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception as exc:
        print(f"⚠️ Failed to write material tuning summary txt: {exc}")

    return {
        "success": success,
        "time": total_time,
        "baseline_dir": baseline_dir,
        "tuned_dir": tuned_dir,
        "plan_file": plan_path,
        "comparison_file": comparison_path,
        "material_selection": proposal.get("material_selection", {}),
        "summary_file": summary_txt,
        "baseline_result": baseline_result,
        "tuned_result": tuned_result,
        "targets": proposal.get("targets", []),
    }


def _run_full_analysis(args, stl_directory, num_stl, base_output_dir, run_context_banner, tests_filter=None):
    """Execute the seasonal test suite with logging already configured."""
    print(run_context_banner)
    tests_filter = tests_filter or ["all"]

    agent = InstrumentedAgent(
        api_key=OPENAI_API_KEY,
        config_file=args.config,
        allow_llm_params=args.allow_llm_params
    )
    print()

    test_cases = [
        {
            "id": "1",
            "name": "Test 1: Northeast Monsoon (Wet Phase) Wind Surge",
            "query": (
                "During the early Northeast monsoon wet phase in December, "
                "assess podium-level wind safety when monsoon surges bring 30 km/h northeasterlies "
                "and saturated air. Highlight downwash risks near public terraces."
            ),
            "params": {
                "cfd": {
                    "wind_speed": 12.0,
                    "wind_direction": 25.0,
                    "temperature": 26.0,
                    "humidity": 92.0,
                    "height": 2.0
                },
                "solar": {
                    "DNI": 550.0,
                    "DHI": 220.0
                }
            }
        },
        {
            "id": "2",
            "name": "Test 2: Late Northeast Monsoon (Dry Phase) Solar Gain",
            "query": (
                "In the late Northeast monsoon dry phase (early February), evaluate midday solar gains "
                "and shading priorities for east-facing façades that are windy but relatively dry."
            ),
            "params": {
                "solar": {
                    "DNI": 850.0,
                    "DHI": 110.0,
                    "shading_threshold": 8.0
                },
                "cfd": {
                    "wind_speed": 7.0,
                    "wind_direction": 35.0,
                    "temperature": 29.0,
                    "humidity": 58.0,
                    "height": 2.0
                }
            }
        },
        {
            "id": "3",
            "name": "Test 3: Inter-monsoon (April) Thunderstorm Comfort",
            "query": (
                "During the late March–May inter-monsoon afternoons with variable winds and severe thunderstorms, "
                "recommend ventilation and shading strategies for plazas and sheltered walkways."
            ),
            "params": {
                "cfd": {
                    "wind_speed": 4.0,
                    "wind_direction": 150.0,
                    "temperature": 32.0,
                    "humidity": 75.0,
                    "height": 2.0
                },
                "solar": {
                    "DNI": 650.0,
                    "DHI": 260.0
                }
            }
        },
        {
            "id": "4",
            "name": "Test 4: Southwest Monsoon Sumatra Squall Resilience",
            "query": (
                "During the Southwest monsoon (July) when Sumatra squalls drive 60 km/h southerly gusts "
                "before noon, run a full environmental analysis to check wind comfort and solar exposure."
            ),
            "params": {
                "cfd": {
                    "wind_speed": 17.0,
                    "wind_direction": 190.0,
                    "temperature": 28.0,
                    "humidity": 80.0,
                    "height": 2.0
                },
                "solar": {
                    "DNI": 720.0,
                    "DHI": 200.0
                }
            }
        },
        {
            "id": "5",
            "name": "Test 5: Fully Coupled Heat & Wind Comfort Audit",
            "query": (
                "Run a fully coupled CFD + solar audit representative of the late March–May inter-monsoon window, "
                "emphasizing district comfort and energy demand while flagging specific hotspots or inefficient pockets."
            ),
            "params": {
                "timestamp": "2025-04-23 15:00",  # Fixed timestamp for reproducibility
                "cfd": {
                    "temperature": 31.5,
                    "humidity": 70.0,
                    "height": 2.0
                },
                "solar": {
                    "DNI": 780.0,
                    "DHI": 240.0,
                    "shading_threshold": 6.0
                }
            }
        },
        {
            "id": "5m",
            "name": "Test 5 + Material Tuning Loop",
            "pipeline": "material_tuning",
            "query": (
                "Run a fully coupled CFD + solar audit representative of the late March–May inter-monsoon window, "
                "emphasizing district comfort and energy demand while flagging specific hotspots or inefficient pockets; "
                "then propose and apply material changes (albedo/emissivity) per material_properties.md to improve thermal "
                "comfort and reduce cooling load, rerun, and compare before/after."
            ),
            "params": {
                "timestamp": "2025-04-23 15:00",  # Fixed timestamp for reproducibility
                "cfd": {
                    "temperature": 31.5,
                    "humidity": 70.0,
                    "height": 2.0
                },
                "solar": {
                    "DNI": 780.0,
                    "DHI": 240.0,
                    "shading_threshold": 6.0
                }
            }
        }
    ]

    normalized_filter = []
    for token in tests_filter:
        lowered = token.lower()
        if lowered == "coupled":
            normalized_filter.append("5")
        elif lowered in ("material", "mat", "matopt", "5m", "5+"):
            normalized_filter.append("5m")
        else:
            normalized_filter.append(lowered)

    # If material-tuning switch is on, swap Test 5 to 5m; for "all", prefer 5m over 5.
    if args.material_tuning:
        normalized_filter = [
            "5m" if t == "5" else t
            for t in normalized_filter
        ]

    if "all" in normalized_filter:
        if args.material_tuning:
            normalized_filter = ["1", "2", "3", "4", "5m"]
        else:
            normalized_filter = ["1", "2", "3", "4", "5"]

    selected_ids = set(normalized_filter)
    active_tests = [test for test in test_cases if test["id"] in selected_ids]

    if not active_tests:
        raise ValueError(f"No tests matched selection: {tests_filter}")

    print("\n💡 Selected Test Cases:")
    for test in active_tests:
        print(f"   Test {test['id']}: {test['name']}")
    print("\n⏱️  Estimated total time scales with selected tests (≈10-15 min each)")
    print("="*80 + "\n")

    print("🛈 Tip: Use --tests to choose a subset, e.g. '--tests 2 5' or '--tests coupled'")

    all_results = []

    total_tests = len(active_tests)

    for idx, test in enumerate(active_tests, 1):
        print(f"\n{'='*80}")
        print(f"Running Test {test['id']} ({idx}/{total_tests}): {test['name']}")
        print(f"{'='*80}")
        print(f"Query: {test['query']}\n")

        start_time = time.time()
        test_slug = f"test_{int(test['id']):02d}" if test['id'].isdigit() else f"test_{test['id']}"
        test_output_dir = os.path.join(base_output_dir, test_slug)
        os.makedirs(test_output_dir, exist_ok=True)

        if test.get("pipeline") == "material_tuning":
            bundle = run_material_tuning_test(agent, test, stl_directory, test_output_dir)
            total_time = bundle["time"]
            all_results.append({
                'test_id': test['id'],
                'test_name': test['name'],
                'query': test['query'],
                'success': bundle['success'],
                'time': total_time,
                'summary_file': bundle.get('comparison_file', ''),
                'llm_file': '',
                'output_directory': test_output_dir,
                'plan_file': bundle.get('plan_file', ''),
                'baseline_output': bundle.get('baseline_dir', ''),
                'tuned_output': bundle.get('tuned_dir', '')
            })

            print(f"\n{'='*80}")
            print(f"Test {test['id']} (Material Tuning) Results")
            print(f"{'='*80}")
            print(f"✅ Success: {bundle['success']}")
            print(f"⏱️  Test time: {total_time:.2f}s")
            print(f"📂 Baseline: {bundle.get('baseline_dir', test_output_dir)}")
            print(f"📂 Tuned: {bundle.get('tuned_dir', test_output_dir)}")
            print(f"📄 Plan: {bundle.get('plan_file', '')}")
            print(f"📄 Comparison: {bundle.get('comparison_file', '')}\n")
            if idx < total_tests:
                print(f"\n⏭️  Moving to next test...")
            continue

        result = agent.analyze(
            query=test['query'],
            stl_directory=stl_directory,
            user_parameters=test['params'],
            output_directory=test_output_dir
        )

        total_time = time.time() - start_time

        test_recorder = LLMInteractionRecorder(output_dir=test_output_dir)
        test_recorder.interactions = agent.get_llm_interactions()
        test_recorder.save_summary(result, user_query=test['query'])

        all_results.append({
            'test_id': test['id'],
            'test_name': test['name'],
            'query': test['query'],
            'success': result['success'],
            'time': total_time,
            'summary_file': test_recorder.summary_file,
            'llm_file': test_recorder.log_file,
            'output_directory': result.get('output_directory', test_output_dir)
        })

        print(f"\n{'='*80}")
        print(f"Test {test['id']} Results")
        print(f"{'='*80}")
        print(f"✅ Success: {result['success']}")
        print(f"⏱️  Test time: {total_time:.2f}s")
        print(f"📂 Outputs: {result.get('output_directory', test_output_dir)}\n")

        if result.get('output_files'):
            files = result['output_files']
            print("📁 Generated Files:")
            print("\n📊 Data Files:")
            for f in files.get('csv_files', []):
                print(f"   • {f['solver']}: {f['file']}")
            print("\n🎨 Visualization Files:")
            for f in files.get('visualization_files', []):
                print(f"   • {f['solver']}: {f['file']}")
            if files.get('artifact_files'):
                print("\n📦 Coupled Outputs:")
                for f in files.get('artifact_files', []):
                    print(f"   • {f['solver']}: {f['file']}")

        print(f"\n📝 Test {test['id']} Record Files:")
        print(f"   🤖 LLM: {test_recorder.log_file}")
        print(f"   📄 Summary: {test_recorder.summary_file}")

        if idx < total_tests:
            print(f"\n⏭️  Moving to next test...")

    print(f"\n\n{'='*80}")
    print("🎉 ALL TESTS COMPLETED")
    print(f"{'='*80}\n")

    print("📊 Summary of All Tests:")
    print(f"{'='*80}")
    for res in all_results:
        status = "✅" if res['success'] else "❌"
        print(f"\nTest {res['test_id']}: {res['test_name']}")
        print(f"  Status: {status}")
        print(f"  Query: {res['query']}")
        print(f"  Time: {res['time']:.1f}s")
        print(f"  Summary: {res['summary_file']}")
        print(f"  Output: {res['output_directory']}")
        if res.get("plan_file"):
            print(f"  Material plan: {res.get('plan_file')}")
        if res.get("baseline_output"):
            print(f"  Baseline run: {res.get('baseline_output')}")
        if res.get("tuned_output"):
            print(f"  Tuned run: {res.get('tuned_output')}")

    total_time_all = sum(r['time'] for r in all_results)
    success_count = sum(1 for r in all_results if r['success'])

    print(f"\n{'='*80}")
    print(f"Total Tests: {len(all_results)}")
    print(f"Successful: {success_count}/{len(all_results)}")
    print(f"Total Time: {total_time_all:.1f}s ({total_time_all/60:.1f} minutes)")
    print(f"{'='*80}\n")

    print("💡 View all summaries:")
    print(f"   ls -lht {base_output_dir}/*/analysis_summary_*.txt | head -4")
    print("\n💡 View latest summary:")
    print(f"   cat {base_output_dir}/*/analysis_summary_*.txt | head -30")
    print("\n📁 All results saved to:")
    print(f"   📊 Data files: {base_output_dir}/")
    print(f"   🎨 Visualizations: {base_output_dir}/")
    print(f"   📝 LLM logs: {base_output_dir}/")
    print(f"   📄 Summaries: {base_output_dir}/")


def main():
    """Run complete analysis and record all processes"""
    args = parse_arguments()

    stl_directory = args.stl_directory
    num_stl = len([f for f in os.listdir(stl_directory) if f.lower().endswith(".stl")])
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_output_dir = os.path.join("/scratch/Urban/intelligent_agent_package/results", f"full_analysis_{run_timestamp}")
    os.makedirs(base_output_dir, exist_ok=True)

    run_context_banner = (
        "================================================================================\n"
        "🚀 Complete Building Analysis - with LLM Interaction Recording\n"
        "================================================================================\n"
        "📝 Will record:\n"
        "   ✅ All LLM interactions (Requests and Responses)\n"
        "   ✅ CFD/Solar visualization results\n"
        "   ✅ Analysis summary report\n"
        "   ✅ User query in summary\n\n"
        "⚙️  Configuration:\n"
        f"   📄 Config file: {args.config}\n"
        f"   🤖 LLM parameters: {'ENABLED (LLM can suggest parameters)' if args.allow_llm_params else 'DISABLED (fixed config + user params)'}\n"
        f"   🧱 Material tuning: {'ON (Test 5 → 5m baseline+tuned)' if args.material_tuning else 'OFF (run baseline only)'}\n"
        "================================================================================\n\n"
        "🏢 Using UrGen Urban District Dataset:\n"
        f"   📁 STL Path: {stl_directory}/\n"
        f"   📊 Buildings: {num_stl} STL files (multi-building district)\n"
        "   📍 Location: Singapore (≈1.379°N, 103.893°E)\n"
        f"   📁 Unified output root: {base_output_dir}/\n"
        "================================================================================\n"
    )

    run_context_md_path = Path(base_output_dir) / "run_context.md"
    run_context_md_path.write_text("# Console Log\n\n", encoding="utf-8")

    with StdoutFileLogger(run_context_md_path, mode="a"):
        _run_full_analysis(
            args,
            stl_directory,
            num_stl,
            base_output_dir,
            run_context_banner,
            tests_filter=args.tests,
        )
    

if __name__ == "__main__":
    main()
