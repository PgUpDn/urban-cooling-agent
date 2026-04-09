# 2 Methodology

The core orchestrator is implemented as a LangGraph-style state machine. At a high level, each run follows five stages:

1. **Intent Analysis.** A GPT-5.1 model reads the user query and proposes which solvers are needed (e.g., geometry, CFD, solar) together with initial parameter suggestions. When material optimization is requested, the agent also plans a baseline-then-tuned execution loop.

2. **Geometry Analysis.** STL files are loaded, cleaned, concatenated, and summarized. Building footprints are extracted and indexed for later cross-referencing with simulation hotspots.

3. **Solver Orchestration.** The agent merges parameters from multiple sources—configuration defaults, climate databases, real-time weather services, LLM advisories, and user overrides—according to a strict priority hierarchy. The merged parameters are then dispatched to the physics backend via thin wrapper classes.

4. **Material Tuning Loop (optional).** For optimization scenarios, the agent executes a baseline simulation, analyzes the results to identify high-load buildings and thermal hotspots, proposes surface property adjustments (albedo, emissivity), reruns the simulation with tuned materials, and computes before/after comparisons.

5. **Integration and Reporting.** The LLM receives compact summaries of solver metrics (cooling load, PET, MRT, wind comfort) and file paths, then drafts a human-readable analysis with actionable design recommendations. All prompts, responses, and parameter snapshots are persisted for full auditability.

---

## 2.1 Agentic AI-Enabled Framework

### 2.1.1 Weather and Parameter Governance

Following best practices from tool-using agents, we make the LLM advisory but not authoritative. The solver ultimately accepts a structured input object whose fields are populated according to the following priority order (lowest to highest):

1. **Configuration defaults:** A JSON configuration file provides structural defaults for simulation parameters (mesh resolution, time stepping, material properties).

2. **Climate database:** The primary source of hourly weather conditions comes from standardized climate files (e.g., IWEC/TMY format), providing representative meteorological data for the target location.

3. **Real-time weather service:** An optional weather client can fetch measurements from public APIs (e.g., national meteorological services). These values only fill parameters that remain unset after the climate database pass.

4. **LLM suggestions:** Intent analysis may propose context-aware refinements (e.g., adjusting wind speed for comfort-focused studies or selecting a representative timestamp for seasonal scenarios). LLM suggestions are applied only if both the climate database and real-time service left the field unset.

5. **User overrides:** Explicit user-supplied parameters have the highest priority and override all other sources.

The final merged parameters are serialized to JSON files (e.g., `final_cfd_parameters.json`, `final_solar_parameters.json`), capturing not just the numeric values but also the provenance chain that produced them. This ensures full transparency and reproducibility.

### 2.1.2 Geometry Analysis Agent

The Geometry Analysis Agent loads all building STL files from the requested directory and performs validation and cleaning. Beyond concatenating individual STLs into a combined geometry file, the agent:

- Extracts XY bounding boxes for each building mesh
- Derives a unique identifier for each building based on file metadata
- Computes geometric statistics (height, footprint area, volume)
- Renders a plan-view index map showing building outlines with ID labels at centroids

This index map serves as a lightweight reference that complements the more detailed CFD and solar visualizations. It answers practical questions such as "which exact building corresponds to this thermal hotspot?" by providing a consistent ID scheme across all outputs.

### 2.1.3 CFD-Solar Execution Agent

For physics simulation, the agent delegates to solver backends via wrapper classes. The wrapper:

- Computes the output directory structure
- Resolves climate file paths
- Forwards the fully merged parameter set to the solver entry point

When radiation and CFD are both enabled, wind, temperature, humidity, and radiative fields evolve consistently over the simulated period (typically a representative 24-hour cycle). The solver outputs include:

| Output Type | Description |
|-------------|-------------|
| VTK slices | Speed, temperature, relative humidity fields at multiple heights and timesteps |
| Surface fields | Surface temperature, MRT, PET on building and ground meshes |
| Screenshots | Rendered visualizations of CFD slices, radiation fields, cooling loads |
| Metrics JSON | Aggregated statistics (total cooling kWh, per-building loads, hotspot coordinates) |

All outputs are referenced by the LLM when composing the final analysis report.

> **Note on solver interchangeability:** The execution agent architecture is designed to be backend-agnostic. The wrapper interface can dispatch to:
> - A **lightweight solver** for rapid prototyping and parameter sweeps
> - A **full-fidelity solver** for detailed coupled CFD-radiation-building energy simulation
> - An **AI surrogate model** for near-instantaneous predictions when trained on sufficient simulation data
>
> This modularity enables scaling from quick exploratory analyses to high-resolution design validation without changing the agent workflow.

### 2.1.4 Material Tuning Pipeline

For scenarios requesting material optimization, the agent implements an automated baseline-then-tuned workflow:

**Step 1: Baseline Simulation**
- Execute coupled CFD-solar simulation with default material properties
- Extract analysis metrics: per-building cooling loads, ground-level PET/MRT hotspots

**Step 2: Material Proposal**
- Identify target buildings (highest cooling demand, proximity to thermal hotspots)
- Propose surface property adjustments based on heuristics and best practices:

| Surface | Baseline | Proposed | Rationale |
|---------|----------|----------|-----------|
| Roof albedo | 0.60 | 0.72 | Cool-roof range to reduce solar heat gains |
| Wall albedo | 0.40 | 0.55 | Lighten façades to cut solar absorption |
| Ground albedo | 0.20 | 0.25 | Modest increase to ease pedestrian MRT |
| Roof emissivity | 0.90 | 0.93 | Enhance longwave re-radiation |
| Wall emissivity | 0.92 | 0.94 | Improve nighttime heat shedding |

**Step 3: Tuned Simulation**
- Rerun the simulation with proposed material properties
- Reuse cached geometry and ray-tracing data to minimize redundant computation

**Step 4: Comparative Analysis**
- Compute delta metrics: cooling load reduction (kWh and %), peak demand changes
- Identify buildings with largest improvements
- Quantify residual hotspots that require form-based interventions

The pipeline outputs include:
- `material_tuning_plan.json`: Proposed materials and target buildings
- `material_tuning_comparison.json`: Before/after metrics with deltas
- `material_tuning_diff.txt`: Human-readable summary of key changes

### 2.1.5 Result Analysis and Recommendation Agent

The final integration stage goes beyond simply reporting simulation outputs. The LLM is prompted to:

1. **Synthesize multi-domain results** — Correlate CFD wind patterns with solar radiation exposure to explain observed thermal comfort patterns.

2. **Identify design hotspots** — Rank locations by severity (PET, MRT) and attribute causes to specific geometric or material factors.

3. **Quantify intervention impacts** — For material-tuned runs, report percentage improvements in cooling load and identify which building categories benefited most.

4. **Generate actionable recommendations** — Propose specific interventions prioritized by impact:
   - Material retrofits (cool roofs, reflective façades)
   - Shading strategies (canopies, vegetation, louvers)
   - Ventilation enhancements (opening orientations, wind corridors)

5. **Reference output files** — Include paths to relevant VTK files, screenshots, and metrics JSON so users can drill down into detailed spatial data.

This capability transforms raw simulation data into design guidance that practitioners can directly apply, bridging the gap between physics-based analysis and architectural decision-making.

---

## 2.2 System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│              Intelligent Building Analysis Agent                     │
│                  (LangGraph State Machine)                           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
┌───────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Intent        │    │ Parameter       │    │ Weather         │
│ Analysis      │    │ Governance      │    │ Integration     │
│ (GPT-5.1)     │    │ (Priority Merge)│    │ (IWEC/NEA)      │
└───────┬───────┘    └────────┬────────┘    └────────┬────────┘
        │                     │                      │
        └─────────────────────┼──────────────────────┘
                              ▼
        ┌─────────────────────────────────────────────┐
        │            Solver Orchestration              │
        ├─────────────────────────────────────────────┤
        │  ┌─────────┐  ┌─────────┐  ┌─────────────┐  │
        │  │Geometry │  │ CFD     │  │ Solar       │  │
        │  │ Agent   │  │ Wrapper │  │ Wrapper     │  │
        │  └────┬────┘  └────┬────┘  └──────┬──────┘  │
        │       │            │              │         │
        │       ▼            ▼              ▼         │
        │  ┌─────────────────────────────────────┐    │
        │  │   Backend (Interchangeable):        │    │
        │  │   • Lightweight Solver              │    │
        │  │   • Full CFD-Radiation Solver       │    │
        │  │   • AI Surrogate Model              │    │
        │  └─────────────────────────────────────┘    │
        └─────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────┐
        │         Material Tuning Loop (Optional)      │
        │  Baseline → Proposal → Tuned → Comparison    │
        └─────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────┐
        │       Integration & Recommendation           │
        │  • Result synthesis                          │
        │  • Hotspot identification                    │
        │  • Actionable design guidance                │
        │  • Full audit trail                          │
        └─────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Final Report   │
                    │  + Artifacts    │
                    └─────────────────┘
```
