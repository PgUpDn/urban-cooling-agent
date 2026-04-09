"""
FastAPI server wrapping IntelligentBuildingAgent.
Start: cd /home/ubuntu/urban_agent && source .venv/bin/activate && python api_server.py
"""
import asyncio, json, os, sys, threading, time, uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

AGENT_ROOT = Path(__file__).resolve().parent
DEFAULT_STL_DIR = str(AGENT_ROOT / "example_stl" / "town_00002_500_1.352_103.719_-4787_-1522")
RESULTS_ROOT = AGENT_ROOT / "results"
executor = ThreadPoolExecutor(max_workers=2)
sessions: Dict[str, Dict[str, Any]] = {}
agent = None
pending_clarifications: Dict[str, str] = {}

MAX_REQUESTS_PER_IP = 5
ip_request_counts: Dict[str, int] = {}

def _check_rate_limit(ip: str):
    count = ip_request_counts.get(ip, 0)
    if count >= MAX_REQUESTS_PER_IP:
        raise HTTPException(429, f"Rate limit exceeded. Maximum {MAX_REQUESTS_PER_IP} requests per session. Please contact the administrator.")
    ip_request_counts[ip] = count + 1


class _TeeStdout:
    def __init__(self, real):
        self._real = real; self._lock = threading.Lock(); self._buffers: Dict[int, list] = {}
    def register(self, tid):
        with self._lock: self._buffers[tid] = []
    def unregister(self, tid):
        with self._lock: return "".join(self._buffers.pop(tid, []))
    def write(self, data):
        self._real.write(data); tid = threading.get_ident()
        with self._lock:
            if tid in self._buffers: self._buffers[tid].append(data)
    def flush(self): self._real.flush()
    def __getattr__(self, name): return getattr(self._real, name)

_tee = _TeeStdout(sys.stdout); sys.stdout = _tee

def _build_agent():
    from config import OPENAI_API_KEY
    from intelligent_building_agent import IntelligentBuildingAgent
    api_key = os.environ.get("OPENAI_API_KEY") or OPENAI_API_KEY
    config_path = AGENT_ROOT / "solver_parameters.json"
    return IntelligentBuildingAgent(api_key=api_key, config_file=str(config_path) if config_path.exists() else None, allow_llm_params=True)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    global agent; agent = _build_agent(); yield; agent = None

app = FastAPI(title="Urban Cooling Agent API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class ChatRequest(BaseModel):
    message: str; history: List[Dict[str, str]] = []; session_id: Optional[str] = None; pending_query: Optional[str] = None
class AnalyzeRequest(BaseModel):
    query: str; stl_directory: Optional[str] = None; parameters: Optional[Dict[str, Any]] = None

NODE_META = {
    "intent_analyzer":    ("intent_analysis",    15, "Analyzing intent & fetching weather data..."),
    "geometry_analyzer":  ("geometry_analysis",   35, "Parsing STL geometry & computing building envelopes..."),
    "solver_orchestrator":("solver_running",      60, "Running physics solvers (CFD / solar)..."),
    "result_integrator":  ("result_integration",  90, "Integrating results & generating report..."),
    "error_handler":      ("error",              -1, "Error occurred"),
}

def _add_msg(sid, kind, text):
    sessions[sid].setdefault("messages", []).append({"type": kind, "text": text, "timestamp": datetime.now().isoformat()})


def _extract_temporal_and_scenario(agent_instance, query: str) -> dict:
    """Use LLM to check if query has temporal info and build scenario summary."""
    from langchain_core.messages import HumanMessage, SystemMessage
    sys_msg = SystemMessage(content=(
        "You are a temporal information extractor for an urban microclimate simulation system.\n\n"
        "Given a user's analysis request, determine:\n"
        "1. Does the request contain ANY temporal information (month, season, date, time of day, monsoon period, etc.)?\n"
        "2. If yes, summarize the proposed simulation scenario.\n\n"
        "Reply in this EXACT JSON format (no markdown, no extra text):\n"
        '{"has_temporal_info": true/false, "scenario_summary": "..."}\n\n'
        "The scenario_summary should be a concise 2-3 sentence description of what will be simulated, "
        "including: time period, type of analysis (CFD/solar/thermal comfort), and key conditions.\n"
        "If has_temporal_info is false, set scenario_summary to empty string."
    ))
    try:
        resp = agent_instance.llm.invoke([sys_msg, HumanMessage(content=query)])
        text = resp.content.strip()
        if text.startswith("```"): text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(text)
    except Exception as e:
        print(f"[EXTRACT] failed: {e}")
        return {"has_temporal_info": True, "scenario_summary": query}


def _run_analysis_streaming(session_id, query, stl_directory, parameters):
    from intelligent_building_agent import AnalysisRequest, IntelligentAgentState
    from langchain_core.runnables import RunnableConfig
    tid = threading.get_ident(); _tee.register(tid)
    try:
        _add_msg(session_id, "status", "Initialising analysis..."); sessions[session_id].update(status="running", stage="init", progress=5)
        results_root = AGENT_ROOT / "results"; results_root.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S"); output_dir = results_root / f"analysis_{ts}"; output_dir.mkdir(parents=True, exist_ok=True)
        agent.llm_recorder.start_session(output_dir)
        request = AnalysisRequest(query=query, stl_directory=stl_directory, user_parameters=parameters)
        resolved_dt = agent._infer_weather_datetime(request)
        resolved_time_str = resolved_dt.isoformat() if resolved_dt else None
        initial_state = IntelligentAgentState(request=request, required_solvers=[], solver_parameters={}, solver_results={}, external_parameters={}, output_directory=str(output_dir), llm_log_file=agent.llm_recorder.get_log_file() or "", llm_text_log_file=agent.llm_recorder.get_text_log_file() or "", resolved_time=resolved_time_str)
        config = RunnableConfig(tags=[Path(stl_directory).name, query[:40]], metadata={"stl_directory": stl_directory, "user_query": query, "output_directory": str(output_dir)})
        initial_state.runnable_config = config
        _add_msg(session_id, "status", f"Output directory: {output_dir.name}"); final_state = None

        for chunk in agent.graph.stream(initial_state, config=config):
            node_name = list(chunk.keys())[0]; final_state = chunk[node_name]
            meta = NODE_META.get(node_name)
            if meta:
                stage, progress, msg = meta; sessions[session_id].update(stage=stage, progress=progress); _add_msg(session_id, "status", msg)
                state_dict = final_state if isinstance(final_state, dict) else (final_state.__dict__ if hasattr(final_state, '__dict__') else {})
                lp = sessions[session_id].setdefault("live_params", {})

                if node_name == "intent_analyzer":
                    if agent.solver_config:
                        lp["config_parameters"] = agent.solver_config
                    solvers = state_dict.get("required_solvers") or []
                    if solvers: _add_msg(session_id, "info", f"Solvers selected: {', '.join(solvers)}"); lp["required_solvers"] = solvers
                    sp = state_dict.get("solver_parameters") or {}
                    if sp: lp["solver_parameters"] = sp
                    ext = state_dict.get("external_parameters") or {}
                    if ext: lp["external_parameters"] = ext
                    weather = state_dict.get("weather_snapshot") or {}
                    if weather:
                        lp["weather_snapshot"] = weather; meas = (weather.get("snapshot") or {}).get("measurements") or {}
                        if meas:
                            lp["weather"] = meas; parts = []
                            if meas.get("temperature_c") is not None: parts.append(f"T={meas['temperature_c']}C")
                            if meas.get("relative_humidity_pct") is not None: parts.append(f"RH={meas['relative_humidity_pct']}%")
                            if meas.get("wind_speed_ms") is not None: parts.append(f"Wind={meas['wind_speed_ms']}m/s")
                            if parts: _add_msg(session_id, "info", f"Live weather: {', '.join(parts)}")
                    resolved = state_dict.get("resolved_time")
                    if resolved: lp["resolved_time"] = resolved

                elif node_name == "geometry_analyzer":
                    sr = state_dict.get("solver_results") or {}; geo = sr.get("geometry") or {}; stats = geo.get("statistics") or {}
                    if stats: lp["geometry_statistics"] = stats
                    fps = geo.get("footprints") or []; envs = geo.get("building_envelopes") or []
                    if envs: lp["building_envelopes"] = envs
                    count = stats.get("building_count") or len(fps)
                    if count: _add_msg(session_id, "info", f"Geometry: {count} buildings detected"); lp["building_count"] = count

                elif node_name == "solver_orchestrator":
                    sr = state_dict.get("solver_results") or {}
                    for sname in ("cfd", "solar"):
                        res = sr.get(sname) or {}
                        if res.get("success"):
                            _add_msg(session_id, "info", f"{sname.upper()} solver completed"); lp[f"{sname}_success"] = True
                            if sname == "cfd" and res.get("parameters"): lp["cfd_parameters"] = res["parameters"]
                            if res.get("analysis_metrics"): lp[f"{sname}_metrics"] = res["analysis_metrics"]
                            if sname == "cfd":
                                for k in ("pet_time_summary","mrt_time_summary","pet_time_buckets","mrt_time_buckets"):
                                    v = res.get(k)
                                    if v: lp[k] = v
                        elif res.get("error"):
                            _add_msg(session_id, "warning", f"{sname.upper()} error: {res['error']}"); lp[f"{sname}_error"] = res["error"]

        if final_state is None: raise RuntimeError("Graph produced no output")
        d = final_state if isinstance(final_state, dict) else (final_state.__dict__ if hasattr(final_state,'__dict__') else {})
        success = d.get("stage") == "complete"; response = d.get("final_response",""); error = d.get("error_message","")
        solver_results = d.get("solver_results",{}); building_analysis = d.get("building_analysis",""); output_dir_value = d.get("output_directory",str(output_dir))
        output_files = {"csv_files":[],"visualization_files":[],"artifact_files":[]}; artifacts_summary = {}
        if isinstance(solver_results, dict):
            for sn, sr in solver_results.items():
                if not isinstance(sr, dict) or not sr.get("success"): continue
                if sr.get("output_file"): output_files["csv_files"].append({"solver":sn,"file":sr["output_file"]})
                if sr.get("visualization_file"): output_files["visualization_files"].append({"solver":sn,"file":sr["visualization_file"]})
                for vf in sr.get("visualization_files",[]): output_files["visualization_files"].append({"solver":sn,"file":vf})
                if sr.get("artifacts"):
                    artifacts_summary[sn] = sr["artifacts"]
                    for af in sr["artifacts"].get("all_files",[]): output_files["artifact_files"].append({"solver":sn,"file":af})
        result = {"success":success,"response":response,"building_analysis":building_analysis,"solver_results":solver_results,"output_files":output_files,"artifacts":artifacts_summary,"error":error,"output_directory":output_dir_value}
        if success:
            sessions[session_id].update(status="completed",stage="complete",progress=100,results=result); _add_msg(session_id,"status","Analysis complete!")
            if response: _add_msg(session_id,"agent_report",response)
        else:
            et = error or response or "Analysis did not complete"; sessions[session_id].update(status="error",stage="error",progress=-1,error=et,results=result); _add_msg(session_id,"error",et)
    except Exception as exc:
        sessions[session_id].update(status="error",stage="error",progress=-1,error=str(exc)); _add_msg(session_id,"error",str(exc))
    finally:
        sessions[session_id]["console_log"] = _tee.unregister(tid)

def _relativize(fp):
    try: return str(Path(fp).resolve().relative_to(RESULTS_ROOT.resolve()))
    except: return None

def _process_results(raw):
    sr = raw.get("solver_results") or {}; cfd = sr.get("cfd") or {}; geo = sr.get("geometry") or {}
    vis,arts,csvs,ss = [],[],[],[]
    for item in (raw.get("output_files") or {}).get("visualization_files",[]):
        r = _relativize(item.get("file",""))
        if r: vis.append({"solver":item.get("solver"),"url":f"/api/files/{r}"})
    for item in (raw.get("output_files") or {}).get("artifact_files",[]):
        r = _relativize(item.get("file",""))
        if r: arts.append({"solver":item.get("solver"),"url":f"/api/files/{r}","filename":Path(item["file"]).name})
    for item in (raw.get("output_files") or {}).get("csv_files",[]):
        r = _relativize(item.get("file",""))
        if r: csvs.append({"solver":item.get("solver"),"url":f"/api/files/{r}","filename":Path(item["file"]).name})
    for sn, a in (raw.get("artifacts") or {}).items():
        for s in a.get("screenshots",[]):
            r = _relativize(s)
            if r: ss.append({"solver":sn,"url":f"/api/files/{r}"})
    gv = []
    for k in ("visualization_file","topview_file"):
        p = geo.get(k)
        if p:
            r = _relativize(p)
            if r: gv.append({"label":k,"url":f"/api/files/{r}"})
    return {"success":raw.get("success",False),"response":raw.get("response",""),"building_analysis":raw.get("building_analysis",""),"metrics":cfd.get("analysis_metrics") or {},"pet_time_summary":cfd.get("pet_time_summary") or [],"mrt_time_summary":cfd.get("mrt_time_summary") or [],"pet_time_buckets":cfd.get("pet_time_buckets") or {},"mrt_time_buckets":cfd.get("mrt_time_buckets") or {},"cfd_parameters":cfd.get("parameters") or {},"geometry":{"statistics":geo.get("statistics") or {},"footprints":geo.get("footprints") or [],"visualizations":gv},"visualization_files":vis,"screenshots":ss,"artifact_files":arts,"csv_files":csvs,"output_directory":raw.get("output_directory","")}

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health(): return {"status":"ok","agent_ready":agent is not None}

@app.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    if not agent: raise HTTPException(503,"Agent not initialized")
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    client_ip = request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")
    server_pending = pending_clarifications.pop(client_ip, None)
    effective_pending = req.pending_query or server_pending
    print(f"[CHAT] ip={client_ip} message={req.message[:80]!r}  front_pq={req.pending_query!r}  server_pq={server_pending!r}")

    if effective_pending:
        combined = f"{effective_pending}. Time period: {req.message}"
        print(f"[ROUTER] clarification: pending={effective_pending[:60]!r} + reply={req.message[:60]!r}")
        extracted = await asyncio.to_thread(_extract_temporal_and_scenario, agent, combined)
        if not extracted.get("has_temporal_info"):
            pending_clarifications[client_ip] = effective_pending
            return {
                "action": "clarify",
                "query": effective_pending,
                "response": "I still need a specific time period. Could you provide a month, season, or date? For example: \"March afternoon\", \"inter-monsoon period\", or \"15 Dec\".",
            }
        scenario = extracted.get("scenario_summary") or combined
        return {"action": "confirm", "query": combined, "scenario": scenario}

    classify = SystemMessage(content=(
        "You are a strict intent router for an urban microclimate SIMULATION system. "
        "This system can EXECUTE real CFD, solar, wind, and thermal comfort simulations.\n\n"
        "Given the user's message, decide:\n"
        "  A) The user wants to RUN/EXECUTE a simulation or analysis → reply: ANALYZE: <restate the query>\n"
        "  B) The user is just chatting, greeting, or asking a general question → reply: CHAT\n\n"
        "IMPORTANT RULES:\n"
        "- If the user describes a scenario, mentions 'run', 'analyze', 'simulate', 'assess', or describes conditions like 'monsoon period', 'afternoon heat', etc → ANALYZE\n"
        "- If the user says hi, asks about capabilities, or asks general questions → CHAT\n"
        "- The response from a prior assistant message that describes a simulation is NOT a request to run — only the USER's own request counts\n"
    ))
    try:
        cr = await asyncio.to_thread(agent.llm.invoke, [classify, HumanMessage(content=req.message)])
        decision = cr.content.strip()
    except Exception as e: raise HTTPException(502,f"LLM classification failed: {e}")

    if decision.upper().startswith("ANALYZE"):
        query = decision.split(":",1)[1].strip() if ":" in decision else req.message
        print(f"[ROUTER] ANALYZE → extracting temporal info from: {query[:80]!r}")
        extracted = await asyncio.to_thread(_extract_temporal_and_scenario, agent, query)
        if not extracted.get("has_temporal_info"):
            pending_clarifications[client_ip] = query
            print(f"[CLARIFY] stored pending for ip={client_ip}: {query[:60]!r}")
            return {
                "action": "clarify",
                "query": query,
                "response": (
                    "I'd be happy to run that analysis! However, I need a **time period** to determine weather conditions "
                    "and solar angles.\n\nCould you specify when? For example:\n"
                    '- "March afternoon" or "January morning"\n'
                    '- "inter-monsoon period" or "wet season"\n'
                    '- A specific date like "15 Dec"\n\n'
                    "Once you provide the timing, I'll prepare the full scenario for your confirmation."
                ),
            }
        scenario = extracted.get("scenario_summary") or query
        return {"action": "confirm", "query": query, "scenario": scenario}

    ctx = ["You are an Intelligent Building Analysis Agent specialized in urban microclimate analysis, CFD simulations, solar analysis, and thermal comfort assessment."]
    if req.session_id and req.session_id in sessions:
        s = sessions[req.session_id]
        if s.get("status") == "completed" and s.get("results"):
            r = s["results"]; ctx.append(f"\nSimulation completed. Report:\n{r.get('response','')[:2000]}\nAnswer follow-up questions using these results.")
    msgs = [SystemMessage(content="\n".join(ctx))]
    for h in req.history:
        if h.get("role") == "user": msgs.append(HumanMessage(content=h.get("content","")))
        else: msgs.append(AIMessage(content=h.get("content","")))
    msgs.append(HumanMessage(content=req.message))
    try:
        resp = await asyncio.to_thread(agent.llm.invoke, msgs); return {"action":"chat","response":resp.content}
    except Exception as e: raise HTTPException(502,f"LLM failed: {e}")

@app.post("/api/simulation/start")
async def start_simulation(req: AnalyzeRequest):
    if not agent: raise HTTPException(503,"Agent not initialized")
    sid = str(uuid.uuid4()); stl = req.stl_directory or DEFAULT_STL_DIR
    sessions[sid] = {"session_id":sid,"status":"queued","stage":"init","progress":0,"message":"Queued","query":req.query,"stl_directory":stl,"parameters":req.parameters,"results":None,"error":None,"messages":[],"console_log":"","created_at":datetime.now().isoformat()}
    asyncio.get_running_loop().run_in_executor(executor, _run_analysis_streaming, sid, req.query, stl, req.parameters)
    return {"status":"started","sessionId":sid,"message":f"Analysis started: {req.query[:120]}"}

@app.get("/api/simulation/{sid}/status")
async def get_status(sid: str):
    if sid not in sessions: raise HTTPException(404)
    s = sessions[sid]; return {"status":s["status"],"sessionId":sid,"stage":s["stage"],"progress":s["progress"],"message":s.get("message","")}

@app.get("/api/simulation/{sid}/messages")
async def get_messages(sid: str, after: int = 0):
    if sid not in sessions: raise HTTPException(404)
    msgs = sessions[sid].get("messages",[]); return {"messages":msgs[after:],"total":len(msgs),"status":sessions[sid]["status"]}

@app.get("/api/simulation/{sid}/params")
async def get_live_params(sid: str):
    if sid not in sessions: raise HTTPException(404)
    s = sessions[sid]; return {"stage":s["stage"],"status":s["status"],"params":s.get("live_params",{})}

@app.get("/api/simulation/{sid}/results")
async def get_results(sid: str):
    if sid not in sessions: raise HTTPException(404)
    s = sessions[sid]
    if s["status"] != "completed": return {"status":s["status"],"sessionId":sid,"message":s.get("message","")}
    p = _process_results(s["results"]); return {"status":"success","sessionId":sid,"message":p["response"],"results":p}

@app.get("/api/files/{file_path:path}")
async def serve_file(file_path: str):
    fp = (RESULTS_ROOT / file_path).resolve()
    if not str(fp).startswith(str(RESULTS_ROOT.resolve())): raise HTTPException(403)
    if not fp.exists(): raise HTTPException(404)
    return FileResponse(str(fp))

@app.get("/api/stl-directories")
async def list_stl_directories():
    sr = AGENT_ROOT / "example_stl"
    if not sr.exists(): return {"directories":[]}
    return {"directories":[{"name":d.name,"path":str(d)} for d in sorted(sr.iterdir()) if d.is_dir()]}

if __name__ == "__main__":
    import uvicorn; uvicorn.run(app, host="0.0.0.0", port=8001)
