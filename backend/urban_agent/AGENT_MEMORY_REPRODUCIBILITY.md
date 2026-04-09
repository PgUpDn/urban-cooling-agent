# Proposed Additions to Manuscript

> Draft text for insertion into the paper. Addresses four reviewer comments.

---

## A. Agent Memory and State Management

*(Suggested location: Methodology section or Appendix)*

The agentic framework uses a single state object (`IntelligentAgentState`) that is threaded through every stage of the LangGraph workflow — Intent Analysis, Geometry Analysis, Solver Orchestration, and Result Integration. This object carries the user query, resolved simulation timestamp, LLM-suggested parameters, live weather readings, per-solver results, and error state, ensuring full traceability from input to output within a single run.

**Parameter provenance.** Solver parameters are resolved via a four-level priority chain (Table X). At each level a JSON snapshot is persisted to the output directory, so the provenance of every final value is auditable post-run.

| Priority | Source | Snapshot file |
|----------|--------|---------------|
| 1 (lowest) | Static config (`solver_parameters.json`) | — |
| 2 | LLM suggestions from intent analysis | `llm_suggested_parameters.json` |
| 3 | NEA real-time weather API | `external_weather_snapshot.json` |
| 4 (highest) | User-supplied overrides | `final_cfd_parameters.json` |

**LLM logging.** Every LLM call across all agents is recorded by a shared `LLMRecorder` that writes (i) a structured JSON log (`llm_interactions_*.json`) with stage, prompt, response, and latency per call, and (ii) a human-readable verbose text log. Both are flushed after each interaction.

**Building IDs.** Identifiers (e.g. `b000`, `b001`) are derived from STL filenames during geometry analysis and propagated to all downstream outputs: footprint bounding boxes, PET/MRT hotspot attribution, per-building cooling loads in `analysis_metrics.json`, and material-tuning target selection. Geometry results (footprints, envelopes, ray-tracing cache) can be optionally reused across scenario runs via a `reuse_geometry_from` pointer, avoiding redundant mesh processing and Monte Carlo ray work while preserving traceability through the tuned run's own parameter snapshot.

---

## B. Terminology Note

*(Suggested location: footnote or paragraph at the start of Methodology)*

Throughout this paper, **agentic framework** (or equivalently **multi-agent system**) refers to the complete LLM-orchestrated pipeline, including the LangGraph workflow, all sub-agents, solver wrappers, and supporting services. The term **"X Agent"** is reserved for individual components: the Orchestrator Agent (intent parsing, parameter merging, result integration), STL Analysis Agent (geometry loading and LLM-powered insight), Building Query Agent (natural-language Q&A), CFD Solver Agent and Solar Solver Agent (thin wrappers dispatching to the coupled_UrGen_v1 physics backend). Utility modules without autonomous reasoning — NEA Weather Client, LLM Recorder, Artifact Collector — are referred to as services.

---

## C. Reproducibility and Availability

*(Suggested location: end of Methodology or a standalone section before Conclusion)*

To support reproducibility, the following materials will be released in a public GitHub repository upon publication: (1) the full Python source code of all agents and the LangGraph orchestrator; (2) an example Singapore urban district (~110 STL buildings with metadata, UrGen-generated, ~1.38°N 103.89°E); (3) the IWEC weather file for Singapore (8 760 hourly records); (4) pre-configured JSON scenarios for the five seasonal test cases; and (5) a CLI test runner that reproduces all experiments with a single command. A `requirements.txt` and setup script are included for environment reproduction.

For users who cannot run the full physics backend, we document the I/O schema of `agent.analyze()` — input: natural-language query, STL directory path, and optional parameter overrides; output: a dictionary containing LLM-generated narrative, per-solver metrics (cooling load, PET/MRT hotspots, time-bucketed maxima), building-level breakdowns, and paths to all generated artefacts. A simplified pseudo-code of the six-stage pipeline (intent → weather → geometry → parameter merge → solvers → integration) is provided in Appendix X.

The repository will also include sample output logs from one complete run: LLM interaction logs, parameter snapshots at each priority level, PET/MRT time-bucket summaries, and the material-tuning before/after comparison. A Zenodo DOI for the archived version will be added to the final manuscript. In the interim, all materials are available from the corresponding author upon request.

---

*Xinyu Yang — January 2026*
