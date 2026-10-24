import { useCallback, useEffect, useState } from "react";
import { Loader2, Inbox, AlertTriangle } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { toneFor, titleCase } from "@/lib/fmt";
import { Button } from "@/components/ui/button";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";

export function useFetch(path, params, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const key = JSON.stringify(params || {});
  const load = useCallback(async () => {
    if (!path) { setLoading(false); return; }
    setLoading(true); setError(null);
    try { const r = await api.get(path, { params }); setData(r.data); }
    catch (e) { setError(errMsg(e)); }
    finally { setLoading(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, key, ...deps]);
  useEffect(() => { load(); }, [load]);
  return { data, error, loading, reload: load, setData };
}

export function useOptions() {
  const c = useFetch("/classes-overview");
  const s = useFetch("/subjects", { page_size: 200, sort: "name" });
  return { classes: c.data || [], subjects: s.data?.items || [] };
}

export function PageHeader({ title, subtitle, actions, testid }) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between fade-up" data-testid={testid || "page-header"}>
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-foreground">{title}</h1>
        {subtitle && <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>}
        <div className="gold-line w-16 mt-3" />
      </div>
      {actions && <div className="flex flex-wrap gap-2 no-print">{actions}</div>}
    </div>
  );
}

export function StatCard({ icon: Icon, label, value, hint, tone = "navy", testid }) {
  const tones = { navy: "bg-[#0A192F] text-white dark:bg-sky-500/15 dark:text-sky-300", sky: "bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
    gold: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300", green: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
    red: "bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300" };
  return (
    <div className="card-surface p-5 flex items-start gap-4 fade-up" data-testid={testid}>
      {Icon && <div className={`h-11 w-11 rounded-xl grid place-items-center shrink-0 ${tones[tone]}`}><Icon className="h-5 w-5" /></div>}
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{label}</p>
        <p className="text-2xl font-bold font-display mt-1 truncate" data-testid={testid ? `${testid}-value` : undefined}>{value}</p>
        {hint && <p className="text-xs text-muted-foreground mt-0.5">{hint}</p>}
      </div>
    </div>
  );
}

export const Badge = ({ value, label, testid }) => (
  <span data-testid={testid} className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap ${toneFor(value)}`}>{label || titleCase(value)}</span>
);

export const Loading = ({ label = "Loading…" }) => (
  <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground" data-testid="loading-state"><Loader2 className="h-5 w-5 animate-spin" />{label}</div>
);

export const Empty = ({ title = "Nothing here yet", hint, action }) => (
  <div className="flex flex-col items-center justify-center py-14 text-center" data-testid="empty-state">
    <div className="h-12 w-12 rounded-full bg-secondary grid place-items-center mb-3"><Inbox className="h-6 w-6 text-sky-600" /></div>
    <p className="font-semibold">{title}</p>
    {hint && <p className="text-sm text-muted-foreground mt-1 max-w-sm">{hint}</p>}
    {action && <div className="mt-4">{action}</div>}
  </div>
);

export const ErrorBox = ({ message, onRetry }) => (
  <div className="flex flex-col items-center py-12 text-center" data-testid="error-state">
    <AlertTriangle className="h-8 w-8 text-rose-500 mb-2" />
    <p className="font-medium">{message}</p>
    {onRetry && <Button variant="outline" className="mt-3" onClick={onRetry} data-testid="retry-btn">Try again</Button>}
  </div>
);

export function Confirm({ trigger, title = "Are you sure?", description, onConfirm, confirmLabel = "Confirm", destructive = true }) {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>{trigger}</AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader><AlertDialogTitle>{title}</AlertDialogTitle>{description && <AlertDialogDescription>{description}</AlertDialogDescription>}</AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel data-testid="confirm-cancel-btn">Cancel</AlertDialogCancel>
          <AlertDialogAction data-testid="confirm-ok-btn" className={destructive ? "bg-destructive text-destructive-foreground hover:bg-destructive/90" : ""} onClick={onConfirm}>{confirmLabel}</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export const Section = ({ title, action, children, className = "", testid }) => (
  <div className={`card-surface p-5 fade-up ${className}`} data-testid={testid}>
    {(title || action) && <div className="flex items-center justify-between mb-4 gap-2"><h3 className="font-semibold text-base">{title}</h3>{action}</div>}
    {children}
  </div>
);

export const DemoNote = () => (
  <span className="inline-flex items-center rounded-md border border-amber-300/60 bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-800 dark:bg-amber-500/10 dark:text-amber-300" data-testid="demo-data-badge">DEMO DATA</span>
);
