import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Download, Play, Printer, Save, Database, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SelectField, FileField } from "@/components/app/FormDialog";
import { DataTable, SearchInput, useTableState } from "@/components/app/DataTable";
import { useFetch, useOptions, PageHeader, Section, Badge, Loading, Confirm } from "@/components/app/common";
import { api, errMsg, downloadFile, API } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fdatetime, titleCase } from "@/lib/fmt";

const NEEDS = { exam_performance: ["exam"], subject_marks: ["exam", "subject"], attendance_daily: ["class", "date1"], attendance_monthly: ["class", "dates"], low_attendance: ["class", "dates"], enrollment: ["class", "dates", "status"], class_list: ["class", "status"],
  fee_collection: ["class", "dates", "method"], transactions: ["class", "dates", "method", "status"], outstanding: ["class", "status"], leave_summary: ["dates", "status"], transport: ["class"], staff: ["status"] };

export function Reports() {
  const { data: list } = useFetch("/reports"); const { classes, subjects } = useOptions(); const exams = useFetch("/exams", { page_size: 100 });
  const [key, setKey] = useState("enrollment"); const [f, setF] = useState({}); const [res, setRes] = useState(null); const [busy, setBusy] = useState(false);
  const n = NEEDS[key] || []; const set = (k, v) => setF({ ...f, [k]: v });
  const run = async () => { setBusy(true); try { const { data } = await api.get(`/reports/${key}`, { params: f }); setRes(data); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); } };
  return (
    <div className="page" data-testid="reports-page">
      <PageHeader title="Reports & Analytics" subtitle="Filter, view, export to CSV or print to PDF" />
      <Section className="no-print"><div className="flex flex-wrap gap-3 items-end">
        <div className="w-64"><Label className="text-xs">Report</Label><SelectField value={key} onChange={(v) => { setKey(v); setF({}); setRes(null); }} options={(list || []).map((r) => ({ value: r.key, label: r.name }))} testid="report-select" /></div>
        {n.includes("class") && <div className="w-44"><Label className="text-xs">Class</Label><SelectField value={f.class_id || ""} onChange={(v) => set("class_id", v)} allowEmpty="All" options={classes.map((c) => ({ value: c.id, label: c.name }))} testid="report-class" /></div>}
        {n.includes("exam") && <div className="w-64"><Label className="text-xs">Exam</Label><SelectField value={f.exam_id || ""} onChange={(v) => set("exam_id", v)} options={(exams.data?.items || []).map((e) => ({ value: e.id, label: `${e.name} · ${e.class_name}` }))} testid="report-exam" /></div>}
        {n.includes("subject") && <div className="w-44"><Label className="text-xs">Subject</Label><SelectField value={f.subject_id || ""} onChange={(v) => set("subject_id", v)} allowEmpty="All" options={subjects.map((s) => ({ value: s.id, label: s.name }))} testid="report-subject" /></div>}
        {(n.includes("dates") || n.includes("date1")) && <div><Label className="text-xs">{n.includes("date1") ? "Date" : "From"}</Label><Input type="date" value={f.date_from || ""} onChange={(e) => set("date_from", e.target.value)} data-testid="report-from" /></div>}
        {n.includes("dates") && <div><Label className="text-xs">To</Label><Input type="date" value={f.date_to || ""} onChange={(e) => set("date_to", e.target.value)} data-testid="report-to" /></div>}
        {n.includes("method") && <div className="w-40"><Label className="text-xs">Method</Label><SelectField value={f.method || ""} onChange={(v) => set("method", v)} allowEmpty="All" options={["Cash", "Bank Transfer", "Card", "UPI", "Cheque"].map((m) => ({ value: m, label: m }))} testid="report-method" /></div>}
        {n.includes("status") && <div className="w-40"><Label className="text-xs">Status</Label><Input value={f.status || ""} onChange={(e) => set("status", e.target.value)} placeholder="e.g. active, overdue" data-testid="report-status" /></div>}
        <Button onClick={run} disabled={busy} data-testid="run-report-btn"><Play className="h-4 w-4 mr-1" />Run</Button>
        <Button variant="outline" onClick={() => downloadFile(`/reports/${key}`, { ...f, format: "csv" }, `${key}.csv`).catch((e) => toast.error(errMsg(e)))} data-testid="export-report-btn"><Download className="h-4 w-4 mr-1" />CSV</Button>
        <Button variant="outline" onClick={() => window.print()} disabled={!res} data-testid="print-report-btn"><Printer className="h-4 w-4 mr-1" />Print / PDF</Button></div></Section>
      {res && <Section className="print-area" title={`${res.title} · ${res.total} rows`} testid="report-result"><DataTable rows={res.rows} rowKey="_" testid="report-table" columns={res.columns.map((c) => ({ key: c.key, label: c.label, render: (r) => (typeof r[c.key] === "boolean" ? String(r[c.key]) : r[c.key] ?? "—") }))} /></Section>}
    </div>
  );
}

export function Audit() {
  const t = useTableState(); const { data, loading } = useFetch("/audit-logs", { q: t.q, page: t.page, entity: t.filters.entity });
  return (<div className="page" data-testid="audit-page"><PageHeader title="Audit Logs" subtitle="Every sensitive change, who made it and when" />
    <Section><div className="flex gap-3 mb-4"><SearchInput value={t.q} onChange={t.setSearch} placeholder="Search by user…" testid="audit-search" />
      <div className="w-48"><SelectField value={t.filters.entity || ""} onChange={(v) => t.setFilter("entity", v)} allowEmpty="All modules" options={["students", "teachers", "users", "attendance", "marks", "exams", "invoices", "payments", "settings", "leaves", "auth"].map((e) => ({ value: e, label: e }))} testid="audit-entity" /></div></div>
      <DataTable loading={loading} rows={data?.items} page={t.page} total={data?.total} pageSize={30} onPage={t.setPage} testid="audit-table" columns={[{ key: "created_at", label: "When", render: (r) => fdatetime(r.created_at) },
        { key: "user_name", label: "User", render: (r) => <span>{r.user_name} {r.role && <Badge value={r.role} />}</span> }, { key: "action", label: "Action", render: (r) => titleCase(r.action) }, { key: "entity", label: "Module" },
        { key: "details", label: "Details", className: "max-w-md", render: (r) => <code className="text-[10px] break-all line-clamp-2">{r.details ? JSON.stringify(r.details) : "—"}</code> }]} /></Section></div>);
}

const F = ({ label, children }) => <div className="space-y-1.5"><Label className="text-xs font-semibold">{label}</Label>{children}</div>;

export function Settings() {
  const { loadSchool } = useAuth(); const { data, loading, reload } = useFetch("/settings"); const [s, setS] = useState(null); const [busy, setBusy] = useState(false);
  useEffect(() => { if (data) setS(data); }, [data]);
  if (loading || !s) return <Loading />;
  const set = (k, v) => setS({ ...s, [k]: v });
  const inp = (k, type = "text") => <Input type={type} value={s[k] ?? ""} onChange={(e) => set(k, type === "number" ? Number(e.target.value) : e.target.value)} data-testid={`setting-${k}`} />;
  const sw = (k) => <div><Switch checked={!!s[k]} onCheckedChange={(v) => set(k, v)} data-testid={`setting-${k}`} /></div>;
  const save = async () => { setBusy(true); try { const { integrations, ...body } = s; await api.put("/settings", body); toast.success("Settings saved"); reload(); loadSchool(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); } };
  const json = (k) => <Textarea rows={6} className="font-mono text-xs" defaultValue={JSON.stringify(s[k], null, 1)} onBlur={(e) => { try { set(k, JSON.parse(e.target.value)); } catch { toast.error("Invalid format"); } }} data-testid={`setting-${k}`} />;
  const list = (k) => <Input value={(s[k] || []).join(", ")} onChange={(e) => set(k, e.target.value.split(",").map((x) => x.trim()).filter(Boolean))} data-testid={`setting-${k}`} />;
  const integ = s.integrations || {};
  return (
    <div className="page" data-testid="settings-page">
      <PageHeader title="Settings" subtitle="School configuration. All changes are recorded in the audit log." actions={<Button onClick={save} disabled={busy} data-testid="save-settings-btn"><Save className="h-4 w-4 mr-2" />Save settings</Button>} />
      <Tabs defaultValue="school"><TabsList className="flex-wrap h-auto">{["school", "academic", "attendance", "fees", "security", "integrations", "data"].map((t) => <TabsTrigger key={t} value={t} className="capitalize" data-testid={`settings-tab-${t}`}>{t}</TabsTrigger>)}</TabsList>
        <TabsContent value="school"><Section><div className="grid sm:grid-cols-2 gap-4">
          <F label="School name">{inp("school_name")}</F><F label="Tagline">{inp("tagline")}</F><F label="Email">{inp("email")}</F><F label="Phone">{inp("phone")}</F><F label="Website">{inp("website")}</F>
          <F label="Logo"><FileField value={s.logo_file_id} onChange={(v) => set("logo_file_id", v)} context="logo" accept="image/*" testid="setting-logo" /></F>
          <F label="Address">{inp("address")}</F><F label="Currency">{inp("currency")}</F><F label="Currency symbol">{inp("currency_symbol")}</F><F label="Date format">{inp("date_format")}</F><F label="Time zone (IANA)">{inp("timezone")}</F>
          <F label="Receipt footer">{inp("receipt_footer")}</F></div></Section></TabsContent>
        <TabsContent value="academic"><Section><div className="grid sm:grid-cols-2 gap-4">
          <F label="Current academic year">{inp("academic_year")}</F><F label="Terms (comma separated)">{list("terms")}</F><F label="Working days">{list("working_days")}</F><F label="Gender options">{list("genders")}</F>
          <F label="Overall pass percentage">{inp("pass_percent", "number")}</F><F label="Allow students to edit phone/address">{sw("allow_student_profile_edit")}</F>
          <F label="Grading rules [{min, grade}]">{json("grading")}</F><F label="Periods [{no, start, end, type: class|break|lunch}]">{json("periods")}</F></div></Section></TabsContent>
        <TabsContent value="attendance"><Section><div className="grid sm:grid-cols-2 gap-4">
          <F label="Low attendance threshold (%)">{inp("low_attendance_threshold", "number")}</F><F label="Teachers may correct past attendance">{sw("teacher_edit_past_attendance")}</F>
          <F label="Student leave approver"><SelectField value={s.student_leave_approver} onChange={(v) => set("student_leave_approver", v)} options={[{ value: "admin", label: "Administrators only" }, { value: "class_teacher", label: "Class teacher or administrator" }]} testid="setting-approver" /></F>
          <F label="Mark approved leave days as Excused">{sw("auto_excuse_on_leave")}</F></div></Section></TabsContent>
        <TabsContent value="fees"><Section><div className="grid sm:grid-cols-2 gap-4">
          <F label="Late fee amount (₹, applied manually to overdue invoices)">{inp("late_fee_amount", "number")}</F><F label="Payment methods">{list("payment_methods")}</F>
          <F label="Library fine per day (₹)">{inp("library_fine_per_day", "number")}</F><F label="Library loan period (days)">{inp("library_loan_days", "number")}</F>
          <F label="Automatic fee reminder emails (daily 9 AM)">{sw("fee_reminders_enabled")}</F><F label="Remind parents this many days before due date">{inp("fee_reminder_days_before", "number")}</F></div></Section></TabsContent>
        <TabsContent value="security"><Section><div className="grid sm:grid-cols-2 gap-4">
          <F label="Session timeout (minutes of inactivity before re-auth)">{inp("session_minutes", "number")}</F><F label="Data retention (years)">{inp("retention_years", "number")}</F></div>
          <p className="text-xs text-muted-foreground mt-4">Password policy: minimum 8 characters with letters and numbers. 5 failed logins lock the account for 15 minutes. Roles: Admin, Teacher, Student, Parent — permissions are enforced on the server.</p></Section></TabsContent>
        <TabsContent value="integrations"><Section><div className="space-y-3 text-sm">
          {[["Email notifications (password reset, leave decisions)", integ.email, "email_notifications"], ["Razorpay online payments", integ.razorpay], ["Cashfree online payments", integ.cashfree], ["SMS notifications", integ.sms], ["WhatsApp notifications", integ.whatsapp], ["Live GPS bus tracking", integ.gps]].map(([l, on, k]) => (
            <div key={l} className="flex items-center justify-between border-b pb-2"><span>{l}</span><span className="flex items-center gap-3">{k && sw(k)}<Badge value={on ? "active" : "inactive"} label={on ? "Configured" : "Not configured"} /></span></div>))}
          <p className="text-xs text-muted-foreground">Messages are never shown as sent unless the provider is configured.</p></div></Section></TabsContent>
        <TabsContent value="data"><Section><div className="flex flex-wrap gap-3">
          <a href={`${API}/settings/backup`} data-testid="backup-btn"><Button variant="outline"><Database className="h-4 w-4 mr-2" />Download full backup (JSON)</Button></a>
          <Confirm title="Delete all demo data?" description="This permanently removes every sample student, teacher, invoice and record marked as demo, plus demo logins. Your admin account and settings stay." confirmLabel="Delete demo data"
            onConfirm={() => api.post("/settings/clear-demo").then((r) => toast.success(`${r.data.deleted} demo records removed`)).catch((e) => toast.error(errMsg(e)))} trigger={<Button variant="outline" className="text-rose-600" data-testid="clear-demo-btn"><Trash2 className="h-4 w-4 mr-2" />Remove demo data</Button>} /></div></Section></TabsContent>
      </Tabs>
    </div>
  );
}

export function Profile() {
  const { user, setUser } = useAuth(); const [sp] = useSearchParams(); const p = user.profile || {};
  const [f, setF] = useState({ name: user.name, phone: p.phone || p.guardian_phone || "", address: p.address || "" }); const [pw, setPw] = useState({ current_password: "", new_password: "", confirm: "" });
  const save = async () => { try { const { data } = await api.put("/auth/profile", f); setUser(data); toast.success("Profile updated"); } catch (e) { toast.error(errMsg(e)); } };
  const change = async () => { if (pw.new_password !== pw.confirm) { toast.error("Passwords do not match"); return; } try { await api.post("/auth/change-password", pw); toast.success("Password changed. Other sessions were signed out."); setPw({ current_password: "", new_password: "", confirm: "" }); } catch (e) { toast.error(errMsg(e)); } };
  return (<div className="page max-w-3xl" data-testid="profile-page"><PageHeader title="My Profile" subtitle={`${user.email} · ${user.role}`} />
    <Tabs defaultValue={sp.get("tab") || "profile"}><TabsList><TabsTrigger value="profile">Profile</TabsTrigger><TabsTrigger value="password" data-testid="tab-password">Change password</TabsTrigger></TabsList>
      <TabsContent value="profile"><Section><div className="grid sm:grid-cols-2 gap-4">
        <F label="Name"><Input value={f.name} disabled={user.role !== "admin"} onChange={(e) => setF({ ...f, name: e.target.value })} data-testid="profile-name" /></F>
        {user.role !== "admin" && <><F label="Phone"><Input value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} data-testid="profile-phone" /></F><F label="Address"><Input value={f.address} onChange={(e) => setF({ ...f, address: e.target.value })} data-testid="profile-address" /></F></>}
        {user.role === "student" && <p className="text-xs text-muted-foreground sm:col-span-2">Official records (name, class, marks, attendance, fees) can only be changed by the school.</p>}</div>
        <Button className="mt-4" onClick={save} data-testid="save-profile-btn">Save</Button></Section></TabsContent>
      <TabsContent value="password"><Section><div className="grid gap-4 max-w-sm">
        <F label="Current password"><Input type="password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} data-testid="current-password" /></F>
        <F label="New password"><Input type="password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} data-testid="new-password" /></F>
        <F label="Confirm new password"><Input type="password" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} data-testid="confirm-password" /></F>
        <Button onClick={change} data-testid="change-password-btn">Change password</Button></div></Section></TabsContent></Tabs></div>);
}
