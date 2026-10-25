"use client";

import { useEffect, useState } from "react";
import LineChart from "../../components/LineChart";

const SCHEDULER_ORDER = ["round-robin", "mbfd", "mbfd-migration", "ga", "pso", "aco"];
const COLORS = {
  "round-robin": "#8a96a6",
  mbfd: "#e2605a",
  "mbfd-migration": "#4fd1a5",
  ga: "#e0a940",
  pso: "#5b8dee",
  aco: "#c77dff",
};
const LABELS = {
  "round-robin": "Round robin",
  mbfd: "MBFD",
  "mbfd-migration": "MBFD + migration-aware (ours)",
  ga: "Genetic Algorithm",
  pso: "Particle Swarm",
  aco: "Ant Colony",
};

const CHARTS = [
  { metric: "avg_energy_w", label: "Energy consumption (W)" },
  { metric: "avg_temp_variation_c", label: "Temperature variation (°C)" },
  { metric: "total_carbon_kg", label: "Carbon emissions (kg CO2e)" },
  { metric: "total_migrations", label: "Total migrations" },
];

export default function BenchmarkingPage() {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/benchmark")
      .then((res) => res.json())
      .then((data) => {
        setRows(data.rows || []);
        setError(data.error || null);
      })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, []);

  const present = SCHEDULER_ORDER.filter((name) => rows.some((r) => r.scheduler === name));

  return (
    <>
      <h1>Benchmarking</h1>
      <p className="subtitle">
        Energy, temperature-variation, carbon, and migration-count comparison across all six
        schedulers, read from <code>experiments/results/summary.csv</code>.
      </p>

      {loading && <div className="panel empty-state">Loading...</div>}

      {error && (
        <div className="panel empty-state">
          {error}
          <br />
          Run from the project root:
          <br />
          <code>.venv\Scripts\python.exe experiments\run_experiment.py</code>
        </div>
      )}

      {!loading && !error && rows.length > 0 && (
        <>
          <div className="panel">
            <div className="legend">
              {present.map((name) => (
                <div className="legend-item" key={name}>
                  <span className="legend-swatch" style={{ background: COLORS[name] }} />
                  {LABELS[name]}
                </div>
              ))}
            </div>
            <p className="subtitle" style={{ marginTop: 10, marginBottom: 0 }}>
              round-robin / mbfd / mbfd-migration ran the full 500-3000 task sweep. ga / pso /
              aco ran the same 100 rounds (so arrival density, and the x-axis, stay comparable)
              but over fewer task-volume points (500-1500) -- each re-runs a whole population
              search every round, so trimming volumes instead of rounds keeps the benchmark
              script finishing in minutes instead of hours (see experiments/run_experiment.py).
            </p>
          </div>

          <div className="chart-grid">
            {CHARTS.map(({ metric, label }) => (
              <div className="panel" key={metric}>
                <h2>{label}</h2>
                <LineChart rows={rows} metric={metric} schedulers={present} colors={COLORS} yLabel={label} />
              </div>
            ))}
          </div>
        </>
      )}
    </>
  );
}
