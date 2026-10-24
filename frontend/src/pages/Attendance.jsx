import { useEffect, useState } from "react";
import { Printer, CheckCheck } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SelectField } from "@/components/app/FormDialog";
import { DataTable } from "@/components/app/DataTable";
import { useFetch, PageHeader, Section, Badge, Loading, Empty, StatCard } from "@/components/app/common";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fdate, todayISO, titleCase } from "@/lib/fmt";
import { SaveBar } from "./Academic";

const ST = [["present", "P", "bg-emerald-600"], ["absent", "A", "bg-rose-600"], ["late", "L", "bg-amber-500"], ["excused", "E", "bg-sky-600"]];

function useMySections() {
  const { user } = useAuth();
  const ov = useFetch("/classes-overview"); const asg = useFetch(user.role === "teacher" ? "/assignments" : null);
  const all = (ov.data || []).flatMap((c) => c.sections.map((s) => ({ class_id: c.id, class_name: c.name, section: s.name, class_teacher_id: s.class_teacher_id })));
  if (user.role === "admin") return all;
  const mine = new Set((asg.data || []).map((a) => `${a.class_id}|${a.section}`));
  return all.filter((s) => mine.has(`${s.class_id}|${s.section}`) || s.class_teacher_id === user.profile_id);
}

function MarkSheet() {
  const secs = useMySections();
  const [sel, setSel] = useState(""); const [date, setDate] = useState(todayISO()); const [rows, setRows] = useState(null); const [busy, setBusy] = useState(false); const [marked, setMarked] = useState(false);
  const [c, s] = sel.split("|");
  useEffect(() => {
    if (!sel) return; setRows(null);
    api.get("/attendance/sheet", { params: { date, class_id: c, section: s } }).then((r) => { setRows(r.data.students.map((x) => ({ ...x, status: x.status || "present" }))); setMarked(r.data.already_marked); }).catch((e) => { toast.error(errMsg(e)); setRows([]); });
  }, [sel, date]); // eslint-disable-line
  const setAll = (st) => setRows(rows.map((r) => ({ ...r, status: st })));
  const save = async () => {
    setBusy(true);
    try { const { data } = await api.post("/attendance/sheet", { date, class_id: c, section: s, entries: rows.map((r) => ({ student_id: r.id, status: r.status, remark: r.remark || "" })) });
      toast.success(`Attendance saved for ${rows.length} students${data.corrections ? ` (${data.corrections} corrections logged)` : ""}`); setMarked(true); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const cnt = (st) => rows?.filter((r) => r.status === st).length || 0;
  return (
    <div className="space-y-4">
      <Section><div className="flex flex-wrap gap-3 items-center">
        <div className="w-56"><SelectField value={sel} onChange={setSel} placeholder="Choose class & section" options={secs.map((x) => ({ value: `${x.class_id}|${x.section}`, label: `${x.class_name}-${x.section}` }))} testid="att-section-select" /></div>
        <Input type="date" value={date} max={todayISO()} onChange={(e) => setDate(e.target.value)} className="w-44" data-testid="att-date-input" />
        {marked && <Badge value="submitted" label="Already marked — saving updates records" />}
      </div></Section>
      {!sel ? <Empty title="Select a class and section" hint="Students will load with Present pre-selected." /> : !rows ? <Loading /> : !rows.length ? <Empty title="No active students in this section" /> : <>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">{ST.map(([k]) => <StatCard key={k} label={titleCase(k)} value={cnt(k)} tone={{ present: "green", absent: "red", late: "gold", excused: "sky" }[k]} testid={`att-count-${k}`} />)}</div>
        <Section title={`${rows.length} students · ${fdate(date)}`} action={<div className="flex gap-2">{ST.map(([k, l]) => <Button key={k} size="sm" variant="outline" onClick={() => setAll(k)} data-testid={`mark-all-${k}`}><CheckCheck className="h-3.5 w-3.5 mr-1" />All {l}</Button>)}</div>}>
          <div className="divide-y">{rows.map((r, i) => (
            <div key={r.id} className="flex flex-col sm:flex-row sm:items-center gap-2 py-2.5" data-testid={`att-row-${i}`}>
              <div className="flex-1 min-w-0"><p className="font-medium text-sm">{r.name}</p><p className="text-xs text-muted-foreground">{r.admission_no}</p></div>
              <div className="flex gap-1.5">{ST.map(([k, l, bg]) => <button key={k} onClick={() => setRows(rows.map((x) => (x.id === r.id ? { ...x, status: k } : x)))} aria-label={k} data-testid={`att-${i}-${k}`}
                className={`h-9 w-9 rounded-lg text-sm font-bold transition-all ${r.status === k ? `${bg} text-white scale-105 shadow` : "bg-muted text-muted-foreground hover:bg-muted/70"}`}>{l}</button>)}</div>
              <Input value={r.remark || ""} onChange={(e) => setRows(rows.map((x) => (x.id === r.id ? { ...x, remark: e.target.value } : x)))} placeholder="Remark" className="sm:w-44 h-9" />
            </div>))}</div>
        </Section>
        <SaveBar onSave={save} busy={busy} label="Save attendance" />
      </>}
    </div>
  );
}

function Summary() {
  const secs = useMySections(); const [sel, setSel] = useState(""); const [from, setFrom] = useState(""); const [to, setTo] = useState("");
  const [c, s] = sel.split("|"); const { user } = useAuth();
  const ready = user.role === "admin" || sel;
  const { data, loading } = useFetch(ready ? "/attendance/summary" : null, { class_id: c || "", section: s || "", date_from: from, date_to: to });
  return (
    <div className="space-y-4 print-area">
      <Section><div className="flex flex-wrap gap-3 no-print">
        <div className="w-56"><SelectField value={sel} onChange={setSel} allowEmpty={user.role === "admin" ? "All classes" : undefined} placeholder="Class & section" options={secs.map((x) => ({ value: `${x.class_id}|${x.section}`, label: `${x.class_name}-${x.section}` }))} testid="sum-section-select" /></div>
        <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="w-40" data-testid="sum-from" /><Input type="date" value={to} onChange={(e) => setTo(e.target.value)} className="w-40" data-testid="sum-to" />
        <Button variant="outline" onClick={() => window.print()} data-testid="print-attendance-btn"><Printer className="h-4 w-4 mr-2" />Print report</Button></div>
        <p className="text-xs text-muted-foreground mt-3">Attendance % = (Present + Late) ÷ (Present + Late + Absent). Excused days are not counted. Below {data?.threshold}% is flagged as low.</p></Section>
      {!ready ? <Empty title="Select a class" /> : <Section><DataTable loading={loading} rows={data?.students} testid="att-summary-table" columns={[
        { key: "name", label: "Student", render: (r) => <span>{r.name}<span className="block text-xs text-muted-foreground">{r.admission_no} · {r.class_name}-{r.section}</span></span> },
        { key: "present", label: "P" }, { key: "late", label: "L" }, { key: "absent", label: "A" }, { key: "excused", label: "E" },
        { key: "percentage", label: "%", render: (r) => <span className={r.low ? "text-rose-600 font-bold" : "font-semibold"} data-testid={`att-pct-${r.id}`}>{r.percentage ?? "—"}{r.low && " ⚠"}</span> }]} /></Section>}
    </div>
  );
}

function StaffAttendance() {
  const [date, setDate] = useState(todayISO()); const { data, loading } = useFetch("/staff-attendance", { date }); const [rows, setRows] = useState([]); const [busy, setBusy] = useState(false);
  useEffect(() => { if (data) setRows(data.staff.map((s) => ({ ...s, status: s.status || "present" }))); }, [data]);
  const save = async () => { setBusy(true); try { await api.post("/staff-attendance", { date, entries: rows.map((r) => ({ teacher_id: r.id, status: r.status })) }); toast.success("Staff attendance saved"); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); } };
  return (<div className="space-y-4"><Section><Input type="date" value={date} max={todayISO()} onChange={(e) => setDate(e.target.value)} className="w-44" data-testid="staff-att-date" /></Section>
    {loading ? <Loading /> : <Section><div className="divide-y">{rows.map((r, i) => <div key={r.id} className="flex items-center justify-between py-2 gap-2"><span className="text-sm"><b>{r.name}</b> <span className="text-xs text-muted-foreground">{r.employee_id} · {r.designation}</span></span>
      <div className="w-40"><SelectField value={r.status} onChange={(v) => setRows(rows.map((x) => (x.id === r.id ? { ...x, status: v } : x)))} options={["present", "absent", "late", "half_day", "on_leave"].map((v) => ({ value: v, label: titleCase(v) }))} testid={`staff-att-${i}`} /></div></div>)}</div></Section>}
    <SaveBar onSave={save} busy={busy} label="Save staff attendance" /></div>);
}

function MyAttendance() {
  const { user, childId } = useAuth();
  const sid = user.role === "student" ? user.profile_id : childId;
  const { data, loading } = useFetch(sid ? `/attendance/student/${sid}` : null);
  if (loading || !data) return <Loading />;
  return (<div className="space-y-4">
    <div className="grid grid-cols-2 lg:grid-cols-5 gap-4"><StatCard label="Attendance" value={data.percentage != null ? `${data.percentage}%` : "—"} tone="navy" testid="my-att-pct" />{ST.map(([k]) => <StatCard key={k} label={titleCase(k)} value={data.counts[k]} tone={{ present: "green", absent: "red", late: "gold", excused: "sky" }[k]} />)}</div>
    <Section title="Daily record"><DataTable rows={data.records} rowKey="date" testid="my-att-table" columns={[{ key: "date", label: "Date", render: (r) => fdate(r.date) }, { key: "status", label: "Status", render: (r) => <Badge value={r.status} /> }, { key: "remark", label: "Remark" }]} /></Section></div>);
}

export default function Attendance() {
  const { user } = useAuth();
  return (
    <div className="page" data-testid="attendance-page">
      <PageHeader title="Attendance" subtitle={user.role === "admin" || user.role === "teacher" ? "Mark daily attendance and review percentages" : "Daily and historical attendance"} />
      {user.role === "student" || user.role === "parent" ? <MyAttendance /> :
        <Tabs defaultValue="mark"><TabsList><TabsTrigger value="mark" data-testid="tab-mark">Mark attendance</TabsTrigger><TabsTrigger value="summary" data-testid="tab-summary">Reports</TabsTrigger>{user.role === "admin" && <TabsTrigger value="staff" data-testid="tab-staff">Staff</TabsTrigger>}</TabsList>
          <TabsContent value="mark"><MarkSheet /></TabsContent><TabsContent value="summary"><Summary /></TabsContent>{user.role === "admin" && <TabsContent value="staff"><StaffAttendance /></TabsContent>}</Tabs>}
    </div>
  );
}
