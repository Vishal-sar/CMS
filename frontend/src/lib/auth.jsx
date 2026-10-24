import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { api } from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [school, setSchool] = useState(null);
  const [childId, setChildId] = useState(() => localStorage.getItem("sms_child") || "");

  const loadMe = useCallback(async () => {
    try { const { data } = await api.get("/auth/me"); setUser(data); }
    catch { setUser(false); }
  }, []);
  const loadSchool = useCallback(async () => {
    try { const { data } = await api.get("/settings/public"); setSchool(data); } catch { setSchool({ school_name: "EduPrime School" }); }
  }, []);

  useEffect(() => { loadMe(); loadSchool(); }, [loadMe, loadSchool]);
  useEffect(() => {
    const h = () => setUser((u) => { if (u) sessionStorage.setItem("sms_expired", "1"); return false; });
    window.addEventListener("session-expired", h);
    return () => window.removeEventListener("session-expired", h);
  }, []);

  const logout = async () => { sessionStorage.setItem("sms_loggedout", "1"); try { await api.post("/auth/logout"); } finally { setUser(false); } };
  const pickChild = (id) => { setChildId(id); localStorage.setItem("sms_child", id); };

  return <AuthCtx.Provider value={{ user, setUser, logout, school, loadSchool, reload: loadMe, childId, pickChild }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);

export function Protected({ roles, children }) {
  const { user } = useAuth();
  const loc = useLocation();
  if (user === null) return <div className="min-h-screen grid place-items-center text-muted-foreground" data-testid="auth-loading">Loading…</div>;
  if (!user) return <Navigate to="/login" state={sessionStorage.getItem("sms_loggedout") ? undefined : { from: loc.pathname }} replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/app" replace />;
  return children;
}
