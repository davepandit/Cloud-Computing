// Proxies the Python live_controller's stdlib state server (localhost:8787)
// so the browser never needs CORS or direct network access to it -- the
// fetch happens server-side, inside Next.js.
const CONTROLLER_STATE_URL = "http://127.0.0.1:8787/state";

export async function GET() {
  try {
    const res = await fetch(CONTROLLER_STATE_URL, { cache: "no-store" });
    if (!res.ok) {
      throw new Error(`controller responded ${res.status}`);
    }
    const data = await res.json();
    return Response.json(data);
  } catch (err) {
    return Response.json(
      { error: "controller unreachable", detail: String(err), tick: -1, tasks: [], hosts: [], metrics: {}, events: [] },
      { status: 503 }
    );
  }
}
