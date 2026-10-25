"use client";

// Small hand-rolled SVG line chart -- avoids pulling in a charting
// dependency for what is a handful of simple comparison lines.

const WIDTH = 560;
const HEIGHT = 300;
const PAD = { top: 16, right: 16, bottom: 36, left: 56 };

export default function LineChart({ rows, metric, schedulers, colors, yLabel }) {
  const series = schedulers
    .map((name) => ({
      name,
      points: rows
        .filter((r) => r.scheduler === name)
        .sort((a, b) => a.num_tasks - b.num_tasks),
    }))
    .filter((s) => s.points.length > 0);

  if (series.length === 0) {
    return <div className="empty-state">No data for this metric.</div>;
  }

  const allX = series.flatMap((s) => s.points.map((p) => p.num_tasks));
  const allY = series.flatMap((s) => s.points.map((p) => p[metric]));
  const minX = Math.min(...allX);
  const maxX = Math.max(...allX);
  const minY = 0;
  const maxY = Math.max(...allY) * 1.1 || 1;

  const innerW = WIDTH - PAD.left - PAD.right;
  const innerH = HEIGHT - PAD.top - PAD.bottom;

  const sx = (x) => PAD.left + ((x - minX) / (maxX - minX || 1)) * innerW;
  const sy = (y) => PAD.top + innerH - ((y - minY) / (maxY - minY || 1)) * innerH;

  const yTicks = 4;
  const yTickValues = Array.from({ length: yTicks + 1 }, (_, i) => (maxY / yTicks) * i);
  const xTickValues = [...new Set(allX)].sort((a, b) => a - b);

  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} width="100%" height={HEIGHT}>
      {yTickValues.map((v, i) => (
        <g key={i}>
          <line
            x1={PAD.left}
            x2={WIDTH - PAD.right}
            y1={sy(v)}
            y2={sy(v)}
            stroke="var(--border)"
            strokeWidth="1"
          />
          <text x={PAD.left - 8} y={sy(v)} fontSize="10" fill="var(--muted)" textAnchor="end" dy="3">
            {formatTick(v)}
          </text>
        </g>
      ))}

      {xTickValues.map((v, i) => (
        <text
          key={i}
          x={sx(v)}
          y={HEIGHT - PAD.bottom + 16}
          fontSize="10"
          fill="var(--muted)"
          textAnchor="middle"
        >
          {v}
        </text>
      ))}

      <text
        x={-(HEIGHT / 2)}
        y={14}
        fontSize="11"
        fill="var(--muted)"
        textAnchor="middle"
        transform="rotate(-90)"
      >
        {yLabel}
      </text>
      <text x={WIDTH / 2} y={HEIGHT - 4} fontSize="11" fill="var(--muted)" textAnchor="middle">
        No. of tasks
      </text>

      {series.map((s) => (
        <g key={s.name}>
          <polyline
            fill="none"
            stroke={colors[s.name] || "#999"}
            strokeWidth="2"
            points={s.points.map((p) => `${sx(p.num_tasks)},${sy(p[metric])}`).join(" ")}
          />
          {s.points.map((p, i) => (
            <circle key={i} cx={sx(p.num_tasks)} cy={sy(p[metric])} r="3" fill={colors[s.name] || "#999"} />
          ))}
        </g>
      ))}
    </svg>
  );
}

function formatTick(v) {
  if (v >= 1000) return `${(v / 1000).toFixed(1)}k`;
  if (v < 1) return v.toFixed(3);
  return v.toFixed(1);
}
