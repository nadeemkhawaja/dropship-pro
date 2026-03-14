import { useState } from "react";
import { api } from "../services/api";

export default function Login({ onLogin }) {
  const [user, setUser]   = useState("");
  const [pass, setPass]   = useState("");
  const [err,  setErr]    = useState("");
  const [busy, setBusy]   = useState(false);
  const [show, setShow]   = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!user.trim() || !pass.trim()) { setErr("Enter username and password"); return; }
    setBusy(true); setErr("");
    try {
      const d = await api.login(user.trim(), pass.trim());
      localStorage.setItem("ds_token", d.token);
      localStorage.setItem("ds_user",  d.username);
      onLogin(d.username);
    } catch (ex) {
      setErr(ex.message || "Login failed");
    } finally {
      setBusy(false);
    }
  };

  const inp = {
    width: "100%", padding: "11px 14px", border: "1.5px solid #d1dbe8",
    borderRadius: 9, fontSize: 14, outline: "none", background: "#fff",
    color: "#1e293b", boxSizing: "border-box", transition: "border .15s",
    fontFamily: "Inter, sans-serif",
  };

  return (
    <div style={{
      minHeight: "100vh", background: "#f0f4f8",
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet"/>

      <div style={{
        width: 380, background: "#fff", borderRadius: 18,
        boxShadow: "0 8px 40px rgba(0,0,0,.10)", overflow: "hidden",
      }}>

        {/* Header strip */}
        <div style={{
          background: "linear-gradient(135deg,#1c2e42,#1a3a56)",
          padding: "32px 36px 28px", textAlign: "center",
        }}>
          <div style={{
            width: 52, height: 52, borderRadius: 14, margin: "0 auto 14px",
            background: "linear-gradient(135deg,#1a54cc,#3b44d4)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 26,
          }}>◈</div>
          <div style={{ fontSize: 20, fontWeight: 800, color: "#e2edf8", letterSpacing: "-.3px" }}>
            DropShip Pro
          </div>
          <div style={{ fontSize: 12, color: "#7ab0f8", marginTop: 4, fontFamily: "JetBrains Mono, monospace" }}>
            v4.0 · eBay API
          </div>
        </div>

        {/* Form */}
        <form onSubmit={submit} style={{ padding: "30px 36px 32px" }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: "#1e293b", marginBottom: 20 }}>
            Sign in to continue
          </div>

          {err && (
            <div style={{
              background: "#fef2f2", border: "1px solid #fecaca", color: "#dc2626",
              borderRadius: 8, padding: "9px 13px", fontSize: 13, marginBottom: 16,
            }}>
              {err}
            </div>
          )}

          <div style={{ marginBottom: 14 }}>
            <label style={{ fontSize: 12, fontWeight: 600, color: "#475569",
              display: "block", marginBottom: 6, textTransform: "uppercase", letterSpacing: ".05em" }}>
              Username
            </label>
            <input
              type="text" value={user} onChange={e => setUser(e.target.value)}
              placeholder="your username" autoFocus autoComplete="username"
              style={inp}
              onFocus={e => e.target.style.borderColor = "#1a54cc"}
              onBlur={e  => e.target.style.borderColor = "#d1dbe8"}
            />
          </div>

          <div style={{ marginBottom: 22 }}>
            <label style={{ fontSize: 12, fontWeight: 600, color: "#475569",
              display: "block", marginBottom: 6, textTransform: "uppercase", letterSpacing: ".05em" }}>
              Password
            </label>
            <div style={{ position: "relative" }}>
              <input
                type={show ? "text" : "password"} value={pass}
                onChange={e => setPass(e.target.value)}
                placeholder="••••••••" autoComplete="current-password"
                style={{ ...inp, paddingRight: 44 }}
                onFocus={e => e.target.style.borderColor = "#1a54cc"}
                onBlur={e  => e.target.style.borderColor = "#d1dbe8"}
              />
              <button type="button" onClick={() => setShow(s => !s)} style={{
                position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)",
                background: "none", border: "none", cursor: "pointer",
                color: "#94a3b8", fontSize: 15, padding: 2,
              }}>
                {show ? "🙈" : "👁"}
              </button>
            </div>
          </div>

          <button type="submit" disabled={busy} style={{
            width: "100%", padding: "12px", borderRadius: 10, border: "none",
            background: busy ? "#94a3b8" : "linear-gradient(135deg,#1a54cc,#3b44d4)",
            color: "#fff", fontSize: 14, fontWeight: 700, cursor: busy ? "not-allowed" : "pointer",
            letterSpacing: ".02em", transition: "opacity .15s",
          }}>
            {busy ? "Signing in…" : "Sign In →"}
          </button>
        </form>
      </div>
    </div>
  );
}
