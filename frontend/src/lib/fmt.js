export const inr = (n, sym = "₹") => `${sym}${Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

export function fdate(d) {
  if (!d) return "—";
  const dt = new Date(d.length === 10 ? `${d}T00:00:00` : d);
  if (isNaN(dt)) return d;
  return dt.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}
export const fdatetime = (d) => (d ? new Date(d).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "—");
export const todayISO = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 10); };

const TONES = {
  green: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
  red: "bg-rose-100 text-rose-800 dark:bg-rose-500/15 dark:text-rose-300",
  amber: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  sky: "bg-sky-100 text-sky-800 dark:bg-sky-500/15 dark:text-sky-300",
  slate: "bg-slate-100 text-slate-700 dark:bg-slate-500/15 dark:text-slate-300",
  navy: "bg-[#0A192F] text-white dark:bg-sky-500/20 dark:text-sky-200",
};
const MAP = {
  active: "green", present: "green", paid: "green", success: "green", approved: "green", published: "green", returned: "green", graded: "green", pass: "green", submitted: "sky",
  absent: "red", overdue: "red", failed: "red", rejected: "red", fail: "red", inactive: "slate", archived: "slate", void: "slate", refunded: "slate",
  late: "amber", partial: "amber", pending: "amber", draft: "amber", issued: "sky", unpaid: "amber", excused: "sky", on_leave: "sky", incomplete: "slate",
  admin: "navy", teacher: "sky", student: "green", parent: "amber",
};
export const toneFor = (s) => TONES[MAP[String(s || "").toLowerCase()] || "slate"];
export const titleCase = (s) => String(s || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
