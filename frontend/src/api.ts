import type { Auth } from "./types";

let auth: Auth | null = null;

export function setAuth(a: Auth | null) { auth = a; }
export function getAuth() { return auth; }

function headers(json = true): Record<string, string> {
  const h: Record<string, string> = {};
  if (json) h["Content-Type"] = "application/json";
  if (auth) h["Authorization"] = `Bearer ${auth.token}`;
  return h;
}

async function handle(r: Response) {
  if (!r.ok) {
    const msg = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(msg.detail || "Request failed");
  }
  return r.json();
}

export const api = {
  async login(username: string, password: string): Promise<Auth> {
    const body = new URLSearchParams({ username, password });
    const r = await fetch("/api/auth/login", { method: "POST", body });
    const d = await handle(r);
    return { token: d.access_token, username: d.username, role: d.role };
  },
  async register(username: string, password: string, role: string): Promise<Auth> {
    const r = await fetch("/api/auth/register", {
      method: "POST", headers: headers(), body: JSON.stringify({ username, password, role }),
    });
    const d = await handle(r);
    return { token: d.access_token, username: d.username, role: d.role };
  },
  regions: () => fetch("/api/regions").then(handle),
  risk: (region: string) => fetch(`/api/risk?region=${region}`, { headers: headers(false) }).then(handle),
  compare: (body: any) => fetch("/api/compare", { method: "POST", headers: headers(), body: JSON.stringify(body) }).then(handle),
  recommend: (body: any) => fetch("/api/recommend", { method: "POST", headers: headers(), body: JSON.stringify(body) }).then(handle),
  saveScenario: (body: any) => fetch("/api/scenarios", { method: "POST", headers: headers(), body: JSON.stringify(body) }).then(handle),
  listScenarios: () => fetch("/api/scenarios", { headers: headers(false) }).then(handle),
  runScenario: (id: string, body: any) =>
    fetch(`/api/scenarios/${id}/run`, { method: "POST", headers: headers(), body: JSON.stringify(body) }).then(handle),
  listRuns: (id: string) => fetch(`/api/scenarios/${id}/runs`, { headers: headers(false) }).then(handle),
};
