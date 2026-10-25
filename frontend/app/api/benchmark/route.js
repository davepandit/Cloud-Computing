// Reads experiments/results/summary.csv (produced by
// `python experiments/run_experiment.py` at the repo root) and serves it as
// JSON for the /benchmarking page. No CSV library needed: the file is
// simple, well-formed, comma-separated with no quoted/embedded commas.
import { readFile } from "fs/promises";
import path from "path";

const CSV_PATH = path.join(process.cwd(), "..", "experiments", "results", "summary.csv");

export async function GET() {
  try {
    const text = await readFile(CSV_PATH, "utf-8");
    const lines = text.trim().split(/\r?\n/);
    const header = lines[0].split(",").map((h) => h.trim());
    const rows = lines.slice(1).map((line) => {
      const values = line.split(",").map((v) => v.trim());
      const row = {};
      header.forEach((key, i) => {
        const raw = values[i];
        row[key] = key === "scheduler" ? raw : Number(raw);
      });
      return row;
    });
    return Response.json({ rows });
  } catch (err) {
    return Response.json(
      {
        rows: [],
        error:
          "summary.csv not found -- run `.venv/Scripts/python.exe experiments/run_experiment.py` from the project root first.",
        detail: String(err),
      },
      { status: 404 }
    );
  }
}
