import { useState, useEffect } from "react";
import { Link, useNavigate, useSearchParams, useLocation } from "react-router-dom";
import { Eye, EyeOff, GraduationCap, Loader2, ArrowLeft } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/components/app/Layout";

function Shell({ children, title, subtitle }) {
  const { school } = useAuth();
  useTheme();
  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <div className="relative hidden lg:flex flex-col justify-between bg-[#0A192F] p-12 overflow-hidden">
        <img src="/img/students.jpg" alt="Students" className="absolute inset-0 h-full w-full object-cover opacity-20" />
        <div className="relative flex items-center gap-3"><div className="h-11 w-11 rounded-xl bg-amber-400 grid place-items-center"><GraduationCap className="h-6 w-6 text-[#0A192F]" /></div>
          <span className="font-display font-bold text-white text-xl">{school?.school_name}</span></div>
        <div className="relative"><h2 className="text-4xl font-bold text-white leading-tight">One secure home for<br /><span className="text-amber-400">your whole school.</span></h2>
          <p className="text-slate-300 mt-4 max-w-md">Administrators, teachers, students and parents each get their own portal with access to exactly what they need.</p></div>
        <p className="relative text-xs text-slate-400">{school?.address}</p>
      </div>
      <div className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-md fade-up">
          <Link to="/" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-8" data-testid="back-home-link"><ArrowLeft className="h-4 w-4" />Home</Link>
          <h1 className="text-3xl font-bold">{title}</h1><p className="text-muted-foreground mt-2 mb-8">{subtitle}</p>
          {children}
        </div>
      </div>
    </div>
  );
}

export function Login() {
  const { user, setUser } = useAuth();
  const nav = useNavigate(); const loc = useLocation();
  const [f, setF] = useState({ email: "", password: "", remember: true });
  const [show, setShow] = useState(false); const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  useEffect(() => { if (sessionStorage.getItem("sms_expired")) { setErr("Your session expired. Please sign in again."); sessionStorage.removeItem("sms_expired"); } }, []);
  useEffect(() => { if (user) nav(loc.state?.from || "/app", { replace: true }); }, [user]); // eslint-disable-line
  const submit = async (e) => {
    e.preventDefault(); setErr("");
    if (!f.email || !f.password) { setErr("Enter your email and password"); return; }
    setBusy(true);
    try { const { data } = await api.post("/auth/login", f); setUser(data); toast.success(`Welcome back, ${data.name}`); }
    catch (er) { setErr(errMsg(er)); } finally { setBusy(false); }
  };
  return (
    <Shell title="Sign in" subtitle="Use the credentials provided by your school.">
      <form onSubmit={submit} className="space-y-5" noValidate data-testid="login-form">
        <div className="space-y-1.5"><Label htmlFor="email">Email</Label><Input id="email" type="email" autoComplete="username" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} data-testid="login-email-input" /></div>
        <div className="space-y-1.5"><div className="flex justify-between"><Label htmlFor="pw">Password</Label><Link to="/forgot-password" className="text-xs text-sky-600 hover:underline" data-testid="forgot-password-link">Forgot password?</Link></div>
          <div className="relative"><Input id="pw" type={show ? "text" : "password"} autoComplete="current-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} className="pr-10" data-testid="login-password-input" />
            <button type="button" onClick={() => setShow(!show)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" aria-label={show ? "Hide password" : "Show password"} data-testid="toggle-password-visibility">{show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button></div></div>
        <label className="flex items-center gap-2 text-sm"><Checkbox checked={f.remember} onCheckedChange={(v) => setF({ ...f, remember: !!v })} data-testid="remember-me-checkbox" />Remember me for 7 days</label>
        {err && <p className="text-sm text-rose-600 bg-rose-50 dark:bg-rose-500/10 rounded-lg px-3 py-2" data-testid="login-error">{err}</p>}
        <Button type="submit" className="w-full h-11" disabled={busy} data-testid="login-submit-button">{busy && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}Sign in</Button>
      </form>
      <div className="mt-8 rounded-xl border border-dashed p-4 text-xs text-muted-foreground" data-testid="demo-accounts">
        <p className="font-semibold text-foreground mb-1">Demo portal accounts (demo data)</p>
        <p>Teacher: teacher@eduprime.demo · Student: student@eduprime.demo · Parent: parent@eduprime.demo</p>
        <p className="mt-1">Passwords are shared by your administrator.</p>
      </div>
    </Shell>
  );
}

export function ForgotPassword() {
  const [email, setEmail] = useState(""); const [done, setDone] = useState(""); const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault(); if (!/^\S+@\S+\.\S+$/.test(email)) { toast.error("Enter a valid email"); return; }
    setBusy(true);
    try { const { data } = await api.post("/auth/forgot-password", { email, origin_url: window.location.origin }); setDone(data.message); }
    catch (er) { toast.error(errMsg(er)); } finally { setBusy(false); }
  };
  return (
    <Shell title="Reset your password" subtitle="We'll email you a secure link that expires in 1 hour.">
      {done ? <p className="rounded-lg bg-emerald-50 dark:bg-emerald-500/10 text-emerald-800 dark:text-emerald-300 p-4 text-sm" data-testid="forgot-success">{done}</p> :
        <form onSubmit={submit} className="space-y-5" noValidate>
          <div className="space-y-1.5"><Label>Email</Label><Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} data-testid="forgot-email-input" /></div>
          <Button type="submit" className="w-full h-11" disabled={busy} data-testid="forgot-submit-button">{busy && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}Send reset link</Button>
        </form>}
      <Link to="/login" className="block mt-6 text-sm text-sky-600 hover:underline" data-testid="back-to-login">Back to sign in</Link>
    </Shell>
  );
}

export function ResetPassword() {
  const [sp] = useSearchParams(); const nav = useNavigate();
  const [pw, setPw] = useState(""); const [pw2, setPw2] = useState(""); const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    if (pw.length < 8 || !/\d/.test(pw) || !/[a-z]/i.test(pw)) { toast.error("Use at least 8 characters with letters and numbers"); return; }
    if (pw !== pw2) { toast.error("Passwords do not match"); return; }
    setBusy(true);
    try { await api.post("/auth/reset-password", { token: sp.get("token"), password: pw }); toast.success("Password updated. Please sign in."); nav("/login"); }
    catch (er) { toast.error(errMsg(er)); } finally { setBusy(false); }
  };
  return (
    <Shell title="Choose a new password" subtitle="All other sessions will be signed out.">
      <form onSubmit={submit} className="space-y-5" noValidate>
        <div className="space-y-1.5"><Label>New password</Label><Input type="password" value={pw} onChange={(e) => setPw(e.target.value)} data-testid="reset-password-input" /></div>
        <div className="space-y-1.5"><Label>Confirm password</Label><Input type="password" value={pw2} onChange={(e) => setPw2(e.target.value)} data-testid="reset-password-confirm-input" /></div>
        <Button type="submit" className="w-full h-11" disabled={busy} data-testid="reset-submit-button">Update password</Button>
      </form>
    </Shell>
  );
}
