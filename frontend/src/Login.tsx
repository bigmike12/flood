import { useState } from "react";
import { api } from "./api";
import type { Auth } from "./types";

export default function Login({ onAuth }: { onAuth: (a: Auth) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("coordinator");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(""); setBusy(true);
    try {
      const a = mode === "login"
        ? await api.login(username, password)
        : await api.register(username, password, role);
      onAuth(a);
    } catch (e: any) {
      setErr(e.message || "Failed");
    } finally { setBusy(false); }
  }

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <h1>FloodResQ</h1>
        <p>{mode === "login" ? "Sign in to run and compare response strategies." : "Create a planner or researcher account."}</p>
        <label>Username</label>
        <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        <label>Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        {mode === "register" && (
          <>
            <label>Role</label>
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="coordinator">Emergency coordinator</option>
              <option value="researcher">Researcher</option>
            </select>
          </>
        )}
        <button className="btn" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}</button>
        {err && <div className="err">{err}</div>}
        <div className="switch">
          {mode === "login"
            ? <>No account? <a onClick={() => setMode("register")}>Register</a></>
            : <>Have an account? <a onClick={() => setMode("login")}>Sign in</a></>}
        </div>
        {mode === "login" && <div className="demo">Sign in with the coordinator or admin account provided for this demo.</div>}
      </form>
    </div>
  );
}
