import React, { useState } from 'react';
import type { SimulationResults, LiveParams } from '../types';
import { artifactUrl } from '../services/agentService';

type Tab = 'parameters' | 'geometry' | 'settings';
type TagType = 'live' | 'ai' | 'iwec';

interface ParamSidebarProps { simulationResults?: SimulationResults | null; liveParams?: LiveParams; simRunning?: boolean; }
interface MetricEntry { label: string; value: string; unit: string; source: string; icon: string; color: string; tag?: TagType; }

const TAG: Record<TagType, { bg: string; text: string; label: string }> = {
  live: { bg: 'bg-green-100', text: 'text-green-700', label: 'Live' },
  ai:   { bg: 'bg-indigo-100', text: 'text-indigo-700', label: 'AI' },
  iwec: { bg: 'bg-orange-100', text: 'text-orange-700', label: 'IWEC' },
};

function buildMetrics(lp: LiveParams, r: SimulationResults | null | undefined): MetricEntry[] {
  const m: MetricEntry[] = [];
  const cP = r?.cfd_parameters || lp.cfd_parameters || {};
  const w = lp.weather || {};
  const sp = lp.solver_parameters || {};
  const cS = sp.cfd || {};
  const sS = sp.solar || {};
  const ext = lp.external_parameters || {};
  const eC = ext.cfd || {};
  const cfg = lp.config_parameters || {};
  const cfgC = cfg.cfd || {};
  const cfgS = cfg.solar || {};

  function wt(nea: any, ext: any): { source: string; tag: TagType } {
    return (nea != null || ext != null) ? { source: 'NEA Weather', tag: 'live' } : { source: 'LLM Suggestion', tag: 'ai' };
  }

  // Wind/Temp/Humidity: final CFD params > NEA weather > LLM suggestion > config
  const ws = cP.u_inflow ?? cP.wind_speed ?? w.wind_speed_ms ?? eC.wind_speed ?? cS.wind_speed ?? cfgC.wind_speed;
  if (ws != null) { const i = wt(w.wind_speed_ms, eC.wind_speed); m.push({ label: 'Wind Speed', value: Number(ws).toFixed(1), unit: 'm/s', source: i.source, icon: 'air', color: 'text-blue-500', tag: i.tag }); }

  const wd = cP.wind_direction_deg ?? w.wind_direction_deg ?? eC.wind_direction ?? cS.wind_direction ?? cfgC.wind_direction;
  if (wd != null) { const i = wt(w.wind_direction_deg, eC.wind_direction); m.push({ label: 'Wind Direction', value: String(Math.round(Number(wd))), unit: '\u00B0', source: i.source, icon: 'explore', color: 'text-indigo-500', tag: i.tag }); }

  const tp = cP.T2m_C ?? w.temperature_c ?? eC.temperature ?? cS.temperature ?? cfgC.temperature;
  if (tp != null) { const i = wt(w.temperature_c, eC.temperature); m.push({ label: 'Temperature', value: Number(tp).toFixed(1), unit: '\u00B0C', source: i.source, icon: 'thermostat', color: 'text-red-500', tag: i.tag }); }

  const hm = cP.RH2m_percent ?? w.relative_humidity_pct ?? eC.humidity ?? cS.humidity ?? cfgC.humidity;
  if (hm != null) { const i = wt(w.relative_humidity_pct, eC.humidity); m.push({ label: 'Relative Humidity', value: Number(hm).toFixed(0), unit: '%', source: i.source, icon: 'water_drop', color: 'text-cyan-500', tag: i.tag }); }

  // Solar: LLM suggestion > config (IWEC)
  const dni = sS.DNI ?? cS.DNI ?? cfgS.DNI;
  if (dni != null) m.push({ label: 'Solar DNI', value: String(Math.round(Number(dni))), unit: 'W/m\u00B2', source: 'IWEC Database', icon: 'wb_sunny', color: 'text-orange-500', tag: 'iwec' });

  const dhi = sS.DHI ?? cS.DHI ?? cfgS.DHI;
  if (dhi != null) m.push({ label: 'Solar DHI', value: String(Math.round(Number(dhi))), unit: 'W/m\u00B2', source: 'IWEC Database', icon: 'wb_cloudy', color: 'text-yellow-500', tag: 'iwec' });

  // Material properties (from CFD solver output)
  const alb = cP.rad_albedo_roof ?? cP.albedo_roof;
  if (alb != null) m.push({ label: 'Roof Albedo', value: Number(alb).toFixed(2), unit: '', source: 'AI Material Selection', icon: 'texture', color: 'text-gray-500', tag: 'ai' });

  return m;
}

function buildSolverStatus(lp: LiveParams) {
  return (lp.required_solvers || []).filter(s => s !== 'geometry' && s !== 'query').map(s => ({
    name: s.toUpperCase(),
    status: (lp as any)[`${s}_success`] ? 'success' as const : (lp as any)[`${s}_error`] ? 'error' as const : 'pending' as const,
  }));
}

const Hint: React.FC<{text:string}> = ({text}) => <div className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-500 font-medium flex items-center gap-1.5"><span className="material-icons-outlined text-sm">info</span>{text}</div>;

const MetricCard: React.FC<{m: MetricEntry}> = ({m}) => {
  const t = m.tag ? TAG[m.tag] : null;
  return (
    <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-3 border border-slate-200 dark:border-slate-700">
      <div className="flex items-start justify-between mb-1">
        <div className="flex items-center gap-2 text-slate-700 dark:text-slate-300"><span className={`material-icons-outlined text-lg ${m.color}`}>{m.icon}</span><span className="text-sm font-medium">{m.label}</span></div>
        <span className="text-sm font-bold text-slate-900 dark:text-white">{m.value} {m.unit}</span>
      </div>
      <div className="flex items-center gap-1.5">
        {t && <span className={`px-1.5 py-0.5 ${t.bg} ${t.text} text-[10px] rounded`}>{t.label}</span>}
        <span className="text-[10px] text-slate-500">Source: {m.source}</span>
      </div>
    </div>
  );
};

const ParamsTab: React.FC<{metrics: MetricEntry[]; solvers: ReturnType<typeof buildSolverStatus>; time?: string; has: boolean; running?: boolean}> = ({metrics, solvers, time, has, running}) => (
  <div className="space-y-6">
    {running && <div className="px-3 py-2 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700 font-medium flex items-center gap-1.5"><span className="material-icons-outlined text-sm animate-spin">autorenew</span>Updating as analysis progresses</div>}
    {!running && has && <div className="px-3 py-2 bg-green-50 border border-green-200 rounded-lg text-xs text-green-700 font-medium flex items-center gap-1.5"><span className="material-icons-outlined text-sm">check_circle</span>Parameters from backend</div>}
    {!has && !running && <Hint text="Parameters will appear as the analysis runs" />}
    {time && <div className="bg-primary/5 border border-primary/20 rounded-lg p-3"><div className="flex items-center gap-2 text-primary text-xs font-bold uppercase tracking-wider mb-1"><span className="material-icons-outlined text-sm">schedule</span>Scenario Time</div><p className="text-sm font-medium text-slate-800">{time}</p></div>}
    {solvers.length > 0 && <div><h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Solvers</h3><div className="flex gap-2 flex-wrap">{solvers.map(s => <span key={s.name} className={`px-2.5 py-1 rounded-lg text-xs font-bold flex items-center gap-1 border ${s.status==='success'?'bg-green-50 border-green-200 text-green-700':s.status==='error'?'bg-red-50 border-red-200 text-red-700':'bg-slate-50 border-slate-200 text-slate-500'}`}><span className="material-icons-outlined text-xs">{s.status==='success'?'check_circle':s.status==='error'?'error':'pending'}</span>{s.name}</span>)}</div></div>}
    {metrics.length > 0 && <div><h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Environment (Boundary)</h3><div className="space-y-3">{metrics.map((m,i) => <MetricCard key={i} m={m} />)}</div></div>}
  </div>
);

const GeoTab: React.FC<{lp: LiveParams; r: SimulationResults|null|undefined}> = ({lp, r}) => {
  const gs = r?.geometry?.statistics || lp.geometry_statistics || {};
  const bc = r?.geometry?.statistics?.building_count ?? lp.building_count;
  const fp = r?.geometry?.footprints || [];
  const env = lp.building_envelopes || [];
  const gv = r?.geometry?.visualizations ?? [];
  if (!bc && !gv.length) return <Hint text="Geometry data will appear after geometry analysis" />;
  return (
    <div className="space-y-6">
      {bc != null && <div><h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Overview</h3><div className="grid grid-cols-2 gap-3"><div className="bg-slate-50 rounded-lg p-3 border border-slate-200 text-center"><p className="text-2xl font-bold text-slate-900">{bc}</p><p className="text-[10px] text-slate-500 font-medium mt-0.5">Buildings</p></div>{gs.bounds_min && gs.bounds_max && <div className="bg-slate-50 rounded-lg p-3 border border-slate-200 text-center"><p className="text-lg font-bold text-slate-900">{Math.round(gs.bounds_max[0]-gs.bounds_min[0])}m</p><p className="text-[10px] text-slate-500 font-medium mt-0.5">Domain Width</p></div>}</div></div>}
      {(env.length > 0 || fp.length > 0) && <div><h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Buildings ({env.length||fp.length})</h3><div className="space-y-2 max-h-60 overflow-y-auto">{(env.length>0?env:fp).slice(0,20).map((b:any,i:number) => <div key={i} className="bg-slate-50 rounded-lg p-2.5 border border-slate-200 flex items-center justify-between"><div className="flex items-center gap-2"><span className="material-icons-outlined text-sm text-amber-500">domain</span><span className="text-xs font-medium text-slate-700">{b.id||`b${String(i).padStart(3,'0')}`}</span></div><div className="text-right">{b.height!=null && <span className="text-xs font-bold text-slate-800">{Number(b.height).toFixed(1)}m</span>}{b.roof_area!=null && <span className="text-[10px] text-slate-500 ml-2">{Math.round(b.roof_area)}m2</span>}</div></div>)}</div></div>}
      {gv.length > 0 && <div><h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Visualizations</h3>{gv.map((v,i) => <div key={i} className="mt-2 border border-slate-200 rounded-lg overflow-hidden h-36 relative group cursor-pointer"><img src={artifactUrl(v.url)} alt={v.label} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" /><div className="absolute inset-0 bg-gradient-to-t from-slate-900/80 to-transparent flex items-end p-3"><span className="text-xs text-white font-medium flex items-center gap-1"><span className="material-icons-outlined text-sm">visibility</span>{v.label.replace(/_/g,' ')}</span></div></div>)}</div>}
    </div>
  );
};

const WEATHER_KEYS = new Set(['wind_speed','wind_direction','temperature','humidity','DNI','DHI','GHI','albedo','time']);

const SettingsTab: React.FC<{lp: LiveParams; r: SimulationResults|null|undefined}> = ({lp, r}) => {
  const cP = r?.cfd_parameters || lp.cfd_parameters || {};
  const sp = lp.solver_parameters || {};
  const cS = sp.cfd || {};
  const sS = sp.solar || {};
  const cfg = lp.config_parameters || {};
  const cfgC = cfg.cfd || {};
  const cfgS = cfg.solar || {};

  // CFD solver internals (exclude weather-type params already in Parameters tab)
  const cfdTech: Record<string,any> = {};
  for (const [k, v] of Object.entries({...cfgC, ...cS, ...cP})) {
    if (v != null && typeof v !== 'object' && !WEATHER_KEYS.has(k)) cfdTech[k] = v;
  }

  // Solar solver internals
  const solarTech: Record<string,any> = {};
  for (const [k, v] of Object.entries({...cfgS, ...sS})) {
    if (v != null && typeof v !== 'object' && !WEATHER_KEYS.has(k)) solarTech[k] = v;
  }

  // Data source priority trace
  const sources = [
    { label: 'Highest', desc: 'User-provided parameters', icon: 'person' },
    { label: '3rd', desc: 'NEA live weather API', icon: 'cloud' },
    { label: '2nd', desc: 'LLM-suggested parameters', icon: 'smart_toy' },
    { label: 'Lowest', desc: 'solver_parameters.json config', icon: 'settings' },
  ];

  const hasAnything = Object.keys(cfdTech).length > 0 || Object.keys(solarTech).length > 0;
  if (!hasAnything) return <Hint text="Solver settings will appear after intent analysis" />;

  const kv = (o: Record<string,any>) => Object.entries(o).slice(0, 20).map(([k,v]) => (
    <div key={k} className="flex justify-between items-center py-1.5 border-b border-slate-100 last:border-0">
      <span className="text-xs text-slate-600 font-mono">{k}</span>
      <span className="text-xs font-bold text-slate-800">{typeof v === 'number' ? (Number.isInteger(v) ? String(v) : Number(v).toPrecision(4)) : String(v)}</span>
    </div>
  ));

  return (
    <div className="space-y-6">
      {Object.keys(cfdTech).length > 0 && (
        <div>
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <span className="material-icons-outlined text-sm text-blue-500">air</span>CFD Solver Config
          </h3>
          <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">{kv(cfdTech)}</div>
        </div>
      )}
      {Object.keys(solarTech).length > 0 && (
        <div>
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <span className="material-icons-outlined text-sm text-orange-500">wb_sunny</span>Solar Solver Config
          </h3>
          <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">{kv(solarTech)}</div>
        </div>
      )}
      <div>
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
          <span className="material-icons-outlined text-sm text-slate-500">layers</span>Parameter Priority
        </h3>
        <div className="bg-slate-50 rounded-lg p-3 border border-slate-200 space-y-2">
          {sources.map((s, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className="text-[10px] font-bold text-slate-400 w-12">{s.label}</span>
              <span className="material-icons-outlined text-xs text-slate-400">{s.icon}</span>
              <span className="text-xs text-slate-600">{s.desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export const ParamSidebar: React.FC<ParamSidebarProps> = ({ simulationResults, liveParams = {} as LiveParams, simRunning }) => {
  const [tab, setTab] = useState<Tab>('parameters');
  const has = Object.keys(liveParams).length > 0 || !!simulationResults?.success;
  const metrics = has ? buildMetrics(liveParams, simulationResults) : [];
  const solvers = buildSolverStatus(liveParams);
  return (
    <aside className="w-80 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col shrink-0 mb-4 mr-4 overflow-hidden">
      <div className="flex border-b border-slate-200 dark:border-slate-800">
        {(['parameters','geometry','settings'] as Tab[]).map(t => <button key={t} onClick={() => setTab(t)} className={`flex-1 py-3 text-sm font-medium transition-colors ${tab===t?'text-primary border-b-2 border-primary bg-blue-50/50':'text-slate-500 hover:text-slate-700'}`}>{t.charAt(0).toUpperCase()+t.slice(1)}</button>)}
      </div>
      <div className="p-5 overflow-y-auto flex-1">
        {tab === 'parameters' && <ParamsTab metrics={metrics} solvers={solvers} time={liveParams.resolved_time} has={has} running={simRunning} />}
        {tab === 'geometry' && <GeoTab lp={liveParams} r={simulationResults} />}
        {tab === 'settings' && <SettingsTab lp={liveParams} r={simulationResults} />}
      </div>
    </aside>
  );
};
