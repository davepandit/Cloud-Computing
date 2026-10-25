"use client";

import { useEffect, useState } from "react";

const POLL_MS = 3000;

function timeAgo(ts) {
  if (!ts) return "--";
  const seconds = Math.max(0, Math.round(Date.now() / 1000 - ts));
  return `${seconds}s ago`;
}

export default function DashboardPage() {
  const [state, setState] = useState(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const res = await fetch("/api/state", { cache: "no-store" });
        const data = await res.json();
        if (cancelled) return;
        setConnected(res.ok && data.tick !== -1);
        setState(data);
      } catch {
        if (!cancelled) setConnected(false);
      }
    }

    poll();
    const id = setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const metrics = state?.metrics || {};
  const hosts = state?.hosts || [];
  const tasks = state?.tasks || [];
  const events = state?.events || [];

  return (
    <>
      <h1>Live cluster dashboard</h1>
      <p className="subtitle">
        Polls the live_controller's state server every {POLL_MS / 1000}s.{" "}
        <span className={`badge ${connected ? "connected" : "disconnected"}`}>
          {connected ? "connected" : "controller unreachable"}
        </span>
        {connected && <> &middot; tick {state.tick} &middot; updated {timeAgo(state.timestamp)}</>}
      </p>

      {!connected && (
        <div className="panel empty-state">
          Start the live controller to see real-time data here:
          <br />
          <code>.venv\Scripts\python.exe -m live_controller.loop</code>
        </div>
      )}

      <div className="stat-row">
        <StatCard label="Active tasks" value={tasks.length} />
        <StatCard label="Active hosts" value={metrics.active_hosts ?? "--"} />
        <StatCard label="Power draw" value={metrics.energy_w?.toFixed(0) ?? "--"} unit="W" />
        <StatCard label="Carbon this tick" value={metrics.carbon_kg?.toFixed(4) ?? "--"} unit="kg" />
        <StatCard
          label="Grid carbon intensity"
          value={metrics.carbon_intensity_kg_per_kwh?.toFixed(3) ?? "--"}
          unit="kg/kWh"
        />
        <StatCard label="Temp variation" value={metrics.temp_variation_c?.toFixed(1) ?? "--"} unit="°C" />
      </div>

      <div className="panel">
        <h2>Servers ({hosts.length})</h2>
        {hosts.length === 0 ? (
          <div className="empty-state">No worker nodes reported yet.</div>
        ) : (
          <div className="host-grid">
            {hosts.map((h) => (
              <div key={h.id} className={`host-card status-${h.status}`}>
                <div className="host-name">{h.id}</div>
                <div className="host-tasks">{h.task_count}</div>
                <div>{h.status}</div>
              </div>
            ))}
          </div>
        )}
        <div className="legend">
          <LegendItem color="var(--accent)" label="active (has tasks)" />
          <LegendItem color="var(--muted)" label="idle (ready, no tasks)" />
          <LegendItem color="var(--border)" label="powered off" />
        </div>
      </div>

      <div className="chart-grid">
        <div className="panel">
          <h2>Active tasks ({tasks.length})</h2>
          {tasks.length === 0 ? (
            <div className="empty-state">
              No jobs running. Start the demo workload:
              <br />
              <code>.venv\Scripts\python.exe -m live_controller.demo_workload</code>
            </div>
          ) : (
            <table className="task-table">
              <thead>
                <tr>
                  <th>Task</th>
                  <th>Host</th>
                  <th>CPU (m)</th>
                  <th>Mem (Mi)</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((t) => (
                  <tr key={t.id}>
                    <td>{t.id}</td>
                    <td>{t.host ?? "pending"}</td>
                    <td>{t.cpu_demand?.toFixed(0)}</td>
                    <td>{t.mem_demand?.toFixed(0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="panel">
          <h2>Event log</h2>
          <div className="event-log">
            {events.length === 0 ? (
              <div className="empty-state">No events yet.</div>
            ) : (
              [...events].reverse().map((e, i) => (
                <div key={i} className={`event-row type-${e.type}`}>
                  <span className="event-type">{e.type}</span>
                  {e.message}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </>
  );
}

function StatCard({ label, value, unit }) {
  return (
    <div className="stat-card">
      <div className="label">{label}</div>
      <div className="value">
        {value}
        {unit && <span className="unit">{unit}</span>}
      </div>
    </div>
  );
}

function LegendItem({ color, label }) {
  return (
    <div className="legend-item">
      <span className="legend-swatch" style={{ background: color }} />
      {label}
    </div>
  );
}
