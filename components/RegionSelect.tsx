import React, { useEffect, useRef, useState, useCallback } from 'react';

declare const L: any;

interface Bounds {
  lat_min: number; lat_max: number; lon_min: number; lon_max: number;
}

interface RegionSelectProps {
  selectedStlDir: string | null;
  onRegionConfirmed: (stlDir: string, bounds: Bounds, count: number) => void;
}

const DISTRICTS = [
  { id: '1', name: 'Marina Bay', lat: 1.2847, lng: 103.8597, radius: 600 },
  { id: '2', name: 'Orchard', lat: 1.3048, lng: 103.8318, radius: 500 },
  { id: '3', name: 'Jurong West', lat: 1.3404, lng: 103.7090, radius: 800 },
  { id: '4', name: 'Tampines', lat: 1.3521, lng: 103.9448, radius: 700 },
  { id: '5', name: 'Woodlands', lat: 1.4382, lng: 103.7890, radius: 800 },
  { id: '6', name: 'One North', lat: 1.2995, lng: 103.7872, radius: 600 },
  { id: '7', name: 'NUS', lat: 1.2966, lng: 103.7764, radius: 1200 },
  { id: '8', name: 'NTU', lat: 1.3483, lng: 103.6831, radius: 2000 },
];

const _BACKEND_URL: string = process.env.BACKEND_API_URL || '';
function geoApiBase(): string {
  if (_BACKEND_URL) return _BACKEND_URL.replace(/\/+$/, '') + '/geo-api';
  if (typeof window !== 'undefined' && window.location.pathname.startsWith('/cooling')) return '/cooling/geo-api';
  return '/geo-api';
}

function toBounds(lat: number, lng: number, radius: number): Bounds {
  const latOff = radius / 111320;
  const lngOff = radius / (111320 * Math.cos((lat * Math.PI) / 180));
  return { lat_min: lat - latOff, lat_max: lat + latOff, lon_min: lng - lngOff, lon_max: lng + lngOff };
}

export const RegionSelect: React.FC<RegionSelectProps> = ({ selectedStlDir, onRegionConfirmed }) => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const rectRef = useRef<any>(null);
  const drawControlRef = useRef<any>(null);

  const [bounds, setBounds] = useState<Bounds | null>(null);
  const [buildingCount, setBuildingCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchCount = useCallback(async (b: Bounds) => {
    setLoading(true); setError(null);
    try {
      const qs = `lat_min=${b.lat_min}&lat_max=${b.lat_max}&lon_min=${b.lon_min}&lon_max=${b.lon_max}`;
      const res = await fetch(`${geoApiBase()}/api/region/count?${qs}`);
      if (!res.ok) throw new Error('count failed');
      const data = await res.json();
      setBuildingCount(data.count);
    } catch { setError('Could not reach building server'); setBuildingCount(null); }
    finally { setLoading(false); }
  }, []);

  const showRect = useCallback((b: Bounds) => {
    if (!mapRef.current) return;
    if (rectRef.current) mapRef.current.removeLayer(rectRef.current);
    rectRef.current = L.rectangle(
      [[b.lat_min, b.lon_min], [b.lat_max, b.lon_max]],
      { color: '#2563EB', weight: 2, fillColor: '#2563EB', fillOpacity: 0.12, dashArray: '6,4' },
    ).addTo(mapRef.current);
    mapRef.current.fitBounds(rectRef.current.getBounds(), { padding: [40, 40] });
  }, []);

  const selectBounds = useCallback((b: Bounds) => {
    setBounds(b);
    showRect(b);
    fetchCount(b);
  }, [showRect, fetchCount]);

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;
    const el = mapContainer.current;
    const map = L.map(el, { zoomControl: true }).setView([1.3521, 103.8198], 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors', maxZoom: 19,
    }).addTo(map);

    const t1 = setTimeout(() => map.invalidateSize(), 200);
    const t2 = setTimeout(() => map.invalidateSize(), 600);
    const ro = new ResizeObserver(() => map.invalidateSize());
    ro.observe(el);

    const drawnItems = new L.FeatureGroup();
    map.addLayer(drawnItems);

    const drawControl = new L.Control.Draw({
      position: 'topright',
      draw: { polyline: false, polygon: false, circle: false, circlemarker: false, marker: false, rectangle: { shapeOptions: { color: '#2563EB', weight: 2, fillOpacity: 0.12 } } },
      edit: { featureGroup: drawnItems, remove: true },
    });
    map.addControl(drawControl);
    drawControlRef.current = drawControl;

    map.on(L.Draw.Event.CREATED, (e: any) => {
      drawnItems.clearLayers();
      if (rectRef.current) { map.removeLayer(rectRef.current); rectRef.current = null; }
      const layer = e.layer;
      drawnItems.addLayer(layer);
      const lb = layer.getBounds();
      const b: Bounds = { lat_min: lb.getSouth(), lat_max: lb.getNorth(), lon_min: lb.getWest(), lon_max: lb.getEast() };
      setBounds(b);
      fetchCount(b);
    });

    map.on(L.Draw.Event.DELETED, () => { setBounds(null); setBuildingCount(null); });

    mapRef.current = map;
    return () => { clearTimeout(t1); clearTimeout(t2); ro.disconnect(); map.remove(); mapRef.current = null; };
  }, [fetchCount]);

  const handleDistrictChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const d = DISTRICTS.find(x => x.id === e.target.value);
    if (!d) return;
    const b = toBounds(d.lat, d.lng, d.radius);
    selectBounds(b);
  };

  const handleConfirm = async () => {
    if (!bounds) return;
    setPreparing(true); setError(null);
    try {
      const qs = `lat_min=${bounds.lat_min}&lat_max=${bounds.lat_max}&lon_min=${bounds.lon_min}&lon_max=${bounds.lon_max}`;
      const res = await fetch(`${geoApiBase()}/api/region/prepare?${qs}`, { method: 'POST' });
      if (!res.ok) { const t = await res.text(); throw new Error(t); }
      const data = await res.json();
      onRegionConfirmed(data.stl_directory, data.bounds, data.building_count);
    } catch (err: any) { setError(err.message || 'Failed to prepare region'); }
    finally { setPreparing(false); }
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="p-4 border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 flex items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-3">
          <span className="material-icons-outlined text-primary">map</span>
          <h2 className="text-sm font-semibold">Select Analysis Region</h2>
        </div>
        <div className="flex items-center gap-3">
          <select onChange={handleDistrictChange} defaultValue="" className="text-sm border border-slate-300 dark:border-slate-600 rounded-lg px-3 py-1.5 bg-white dark:bg-slate-800 focus:ring-2 focus:ring-primary">
            <option value="" disabled>Preset district…</option>
            {DISTRICTS.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
          <span className="text-xs text-slate-400">or draw a rectangle on the map</span>
        </div>
      </div>

      <div className="flex-1 relative" style={{ minHeight: 0 }}>
        <div ref={mapContainer} style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, width: '100%', height: '100%' }} />

        <div className="absolute bottom-4 left-4 z-[1000] bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 p-4 min-w-[260px]">
          {selectedStlDir && !bounds && (
            <div className="flex items-center gap-2 text-green-600 text-sm font-medium mb-2">
              <span className="material-icons-outlined text-sm">check_circle</span>
              Region already selected
            </div>
          )}

          {bounds ? (
            <>
              <div className="text-xs text-slate-500 mb-1">Selected Area</div>
              <div className="text-sm font-medium mb-2">
                {bounds.lat_min.toFixed(4)}–{bounds.lat_max.toFixed(4)} N, {bounds.lon_min.toFixed(4)}–{bounds.lon_max.toFixed(4)} E
              </div>
              <div className="flex items-center gap-2 mb-3">
                <span className="material-icons-outlined text-sm text-primary">apartment</span>
                {loading ? (
                  <span className="text-sm text-slate-400">Counting…</span>
                ) : buildingCount !== null ? (
                  <span className="text-sm font-semibold">{buildingCount} buildings</span>
                ) : null}
              </div>
              {error && <div className="text-xs text-red-500 mb-2">{error}</div>}
              <button
                onClick={handleConfirm}
                disabled={preparing || buildingCount === 0}
                className="w-full py-2 px-4 text-sm font-bold text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors shadow-sm disabled:opacity-40 flex items-center justify-center gap-2"
              >
                {preparing ? (
                  <><span className="material-icons-outlined text-sm animate-spin">autorenew</span>Preparing…</>
                ) : (
                  <><span className="material-icons-outlined text-sm">check</span>Use This Region</>
                )}
              </button>
            </>
          ) : (
            <div className="text-sm text-slate-400">
              Pick a preset district or draw a rectangle to select buildings for analysis.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
