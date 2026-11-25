import { useEffect, useRef, useState } from "react";
import Login from "./Login";
import MapView from "./MapView";
import ComparisonChart from "./ComparisonChart";
import { api, setAuth } from "./api";
import type { Auth, Region, Snapshot, StrategyResult, SavedScenario } from "./types";

export default function App() {
  const [auth, setA] = useState<Auth | null>(null);
  if (!auth) return <Login onAuth={(a) => { setAuth(a); setA(a); }} />;
  return <Dashboard auth={auth} onLogout={() => { setAuth(null); setA(null); }} />;
}

function Dashboard({ auth, onLogout }: { auth: Auth; onLogout: () => void }) {
  const [regions, setRegions] = useState<Region[]>([]);
  const [region, setRegion] = useState("lokoja");
  const [intensity, setIntensity] = useState(0.6);
  const [rain, setRain] = useState(60);
  const [strategy, setStrategy] = useState("ai_optimised");
  const [units, setUnits] = useState(20);
  const [seed, setSeed] = useState(42);
  // "experiment" = the Chapter 4 evaluation setup (reproduces the report's table, 30 seeds).
  // "live" = Lokoja-style terrain with the ML risk surface, for the interactive map.
  const [setup, setSetup] = useState<"experiment" | "live">("experiment");
  const compareSeeds = setup === "experiment" ? 30 : 6;

  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [center, setCenter] = useState<[number, number]>([7.802, 6.744]);
  const [status, setStatus] = useState("Ready.");
  const [risk, setRisk] = useState<any[] | null>(null);
  const [rec, setRec] = useState("");
  const [cmp, setCmp] = useState<Record<string, StrategyResult> | null>(null);
  const [saved, setSaved] = useState<SavedScenario[]>([]);
  const [busy, setBusy] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const pausedRef = useRef(false);

  useEffect(() => { api.regions().then(setRegions); refreshLibrary(); }, []);
  useEffect(() => {
    const r = regions.find(x => x.id === region);
    if (r && !wsRef.current) setCenter([r.lat, r.lng]);
  }, [region, regions]);

  function cfg() {
    return { region, flood_intensity: intensity, rainfall_mm: rain, strategy, seed,
             n_responder_units: units, setup };
  }

  function run() {
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    pausedRef.current = false;
    setStatus("Connecting…");
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/run`);
    wsRef.current = ws;
    ws.onopen = () => { ws.send(JSON.stringify({ ...cfg(), delay: 0.1, token: auth.token })); setStatus("Running…"); };
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.type === "init") setCenter([m.center.lat, m.center.lng]);
      else if (m.type === "step") { if (!pausedRef.current) setSnap(m); }
      else if (m.type === "done") setStatus(`Finished. Coverage ${m.kpis.coverage_pct}% · casualties ${m.kpis.casualties}`);
      else if (m.type === "error") setStatus("Error: " + m.message);
    };
    ws.onclose = () => { if (wsRef.current === ws) wsRef.current = null; };
  }
  function reset() { if (wsRef.current) { wsRef.current.close(); wsRef.current = null; } setSnap(null); setStatus("Reset."); }

  async function toggleRisk() {
    if (risk) { setRisk(null); return; }
    setStatus("Loading risk surface…");
    try { const d = await api.risk(region); setRisk(d.cells);
      setStatus(`Risk model: ROC-AUC ${d.metrics.roc_auc} · accuracy ${d.metrics.accuracy}`); }
    catch (e: any) { setStatus(e.message); }
  }

  async function recommend() {
    setBusy(true); setStatus("Optimising & comparing strategies…");
    try {
      const d = await api.recommend({ region, flood_intensity: intensity, rainfall_mm: rain,
                                      seeds: compareSeeds, setup });
      setRec(d.recommendation); setCmp(d.comparison); setStatus("Recommendation ready.");
    } catch (e: any) { setStatus(e.message); } finally { setBusy(false); }
  }
  async function compare() {
    setBusy(true); setStatus(`Running ${compareSeeds}-seed comparison…`);
    try { setCmp(await api.compare({ region, flood_intensity: intensity, rainfall_mm: rain,
                                     seeds: compareSeeds, setup }));
      setStatus("Comparison complete."); }
    catch (e: any) { setStatus(e.message); } finally { setBusy(false); }
  }

  async function refreshLibrary() { try { setSaved(await api.listScenarios()); } catch {} }
  async function saveScenario() {
    const name = prompt("Name this scenario:", `${region} @ intensity ${intensity}`);
    if (!name) return;
    setStatus("Saving scenario…");
    await api.saveScenario({ name, region, flood_intensity: intensity, rainfall_mm: rain,
                             n_responder_units: units, n_ambulances: Math.round(units / 2) });
    setStatus("Scenario saved to database."); refreshLibrary();
  }
  async function runSaved(s: SavedScenario) {
    setStatus(`Running & persisting "${s.name}"…`);
    const d = await api.runScenario(s.id, { strategy, seed });
    setStatus(`Saved run: coverage ${d.kpis.coverage_pct}% · casualties ${d.kpis.casualties}`);
    refreshLibrary();
  }

  const k = snap?.kpis;
  return (
    <div className="app">
      <header>
        <h1>FloodResQ — AI-Driven Flood Disaster Response Simulation Platform</h1>
        <div className="sp">
          <span>{auth.username}</span><span className="role">{auth.role}</span>
          <button className="logout" onClick={onLogout}>Sign out</button>
        </div>
      </header>

      {/* LEFT */}
      <aside className="left">
        <h2>Scenario</h2>
        <label>Setup</label>
        <select value={setup} onChange={(e) => setSetup(e.target.value as "experiment" | "live")}>
          <option value="experiment">Report setup (Chapter 4 numbers)</option>
          <option value="live">Live map (region terrain + risk model)</option>
        </select>
        <div style={{ fontSize: 11, color: "#5A6B7A", margin: "4px 0 8px" }}>
          {setup === "experiment"
            ? "Reproduces the evaluation table exactly (36×36 grid, 30 seeds). Region and risk map are not used in this setup."
            : "Interactive map: the selected region's terrain, a 40×40 grid and the ML risk surface."}
        </div>
        <label>Region</label>
        <select value={region} disabled={setup === "experiment"} onChange={(e) => setRegion(e.target.value)}>
          {regions.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
        </select>
        <label>Flood intensity <span className="v">{intensity.toFixed(2)}</span></label>
        <input type="range" min={0.2} max={1} step={0.05} value={intensity} onChange={e => setIntensity(+e.target.value)} />
        <label>Rainfall (mm) <span className="v">{rain}</span></label>
        <input type="range" min={20} max={160} step={5} value={rain} onChange={e => setRain(+e.target.value)} />
        <label>Allocation strategy</label>
        <select value={strategy} onChange={e => setStrategy(e.target.value)}>
          <option value="ai_optimised">AI-optimised (proposed)</option>
          <option value="nearest">Nearest-depot</option>
          <option value="pop_proportional">Population-proportional</option>
          <option value="random">Random (baseline)</option>
        </select>
        <label>Responder units <span className="v">{units}</span></label>
        <input type="range" min={6} max={30} step={1} value={units} onChange={e => setUnits(+e.target.value)} />
        <label>Random seed <span className="v">{seed}</span></label>
        <input type="range" min={0} max={60} step={1} value={seed} onChange={e => setSeed(+e.target.value)} />

        <h2>Run</h2>
        <button className="btn primary" onClick={run}>▶ Run simulation</button>
        <div className="row">
          <button className="btn ghost" onClick={() => { pausedRef.current = !pausedRef.current; setStatus(pausedRef.current ? "Paused." : "Running…"); }}>Pause</button>
          <button className="btn ghost" onClick={reset}>Reset</button>
        </div>
        <button className="btn ghost" onClick={toggleRisk} disabled={setup === "experiment"}>Toggle risk heat-map</button>
        <button className="btn ghost" onClick={saveScenario}>Save scenario to database</button>
        <div className="status">{status}</div>

        <h2>Map legend</h2>
        <div className="legend">
          <span><i style={{ background: "#7fb0e0" }} />flood</span>
          <span><i style={{ background: "#2e7d32" }} />safe</span>
          <span><i style={{ background: "#e0a72a" }} />at-risk</span>
          <span><i style={{ background: "#dd3333" }} />awaiting</span>
          <span><i style={{ background: "#1C7293" }} />rescued</span>
          <span><i style={{ background: "#111" }} />casualty</span>
          <span><i style={{ background: "#6a1b9a" }} />responder</span>
        </div>
      </aside>

      {/* CENTER */}
      <div className="map"><MapView snap={snap} center={center} risk={risk} /></div>

      {/* RIGHT */}
      <aside className="right">
        <h2>Live indicators <span className="pill">t={snap?.step ?? 0} ({snap?.minute ?? 0} min)</span></h2>
        <div className="kpis">
          <div className="kpi accent"><div className="n">{k?.mean_response_time ?? 0}</div><div className="l">Resp. time (min)</div></div>
          <div className="kpi"><div className="n">{k?.coverage_pct ?? 0}%</div><div className="l">Coverage</div></div>
          <div className="kpi"><div className="n">{k?.rescued ?? 0}</div><div className="l">Rescued</div></div>
          <div className="kpi"><div className="n">{k?.casualties ?? 0}</div><div className="l">Casualties</div></div>
          <div className="kpi"><div className="n">{snap?.flooded_pct ?? 0}%</div><div className="l">Area flooded</div></div>
          <div className="kpi"><div className="n">{snap?.roads_closed_pct ?? 0}%</div><div className="l">Roads closed</div></div>
        </div>

        <h2>AI recommendation</h2>
        <button className="btn ghost" onClick={recommend} disabled={busy}>Get AI recommendation</button>
        {rec && <div className="rec">{rec}</div>}

        <h2>Compare strategies</h2>
        <button className="btn ghost" onClick={compare} disabled={busy}>Run {compareSeeds}-seed comparison</button>
        {cmp && <ComparisonChart data={cmp} />}

        <h2>Saved scenarios (database)</h2>
        <div className="lib">
          {saved.length === 0 && <div style={{ fontSize: 12, color: "#5A6B7A" }}>No saved scenarios yet.</div>}
          {saved.map(s => (
            <div key={s.id} className="item" onClick={() => runSaved(s)} title="Click to run & persist a result">
              <b>{s.name}</b><br />
              <span>{s.region} · intensity {s.flood_intensity} · {s.runs} run(s) saved</span>
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
}
