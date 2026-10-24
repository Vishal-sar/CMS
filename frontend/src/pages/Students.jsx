import { useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { Upload, ArrowUpCircle, Printer, IdCard as IdIcon, ArrowLeft, KeyRound } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import CrudPage from "@/components/app/CrudPage";
import { FormDialog } from "@/components/app/FormDialog";
import { useFetch, useOptions, Badge, Loading, ErrorBox, Section, PageHeader } from "@/components/app/common";
import { api, errMsg, fileUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fdate, todayISO, inr } from "@/lib/fmt";

export function useStudentFields() {
  const { classes } = useOptions();
  const { data: s } = useFetch("/settings");
  const parents = useFetch("/parents", { page_size: 500, sort: "name" });
  const secs = (f) => (classes.find((c) => c.id === f.class_id)?.sections || []).map((x) => ({ value: x.name, label: `Section ${x.name} (${x.student_count}/${x.capacity})` }));
  const fields = [
    { name: "name", label: "Full name", required: true },
    { name: "photo_file_id", label: "Profile photo", type: "file", context: "photo", accept: "image/*" },
    { name: "dob", label: "Date of birth", type: "date", required: true, validate: (v) => (v >= todayISO() ? "Date of birth must be in the past" : null) },
    { name: "gender", label: "Gender", type: "select", required: true, options: (s?.genders || ["Male", "Female", "Other"]).map((g) => ({ value: g, label: g })) },
    { name: "class_id", label: "Class", type: "select", required: true, options: classes.map((c) => ({ value: c.id, label: c.name })), onChange: () => ({ section: "" }) },
    { name: "section", label: "Section", type: "select", required: true, options: secs },
    { name: "academic_year", label: "Academic year", required: true },
    { name: "admission_date", label: "Admission date", type: "date", required: true },
    { name: "blood_group", label: "Blood group", type: "select", allowEmpty: true, options: ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"].map((b) => ({ value: b, label: b })) },
    { name: "status", label: "Enrollment status", type: "select", options: ["active", "inactive", "transferred", "graduated"].map((v) => ({ value: v, label: v[0].toUpperCase() + v.slice(1) })) },
    { name: "guardian_name", label: "Parent / guardian name", required: true },
    { name: "guardian_phone", label: "Parent / guardian phone", required: true, validate: (v) => (!/^[+\d\s-]{6,20}$/.test(v || "") ? "Enter a valid phone" : null) },
    { name: "guardian_email", label: "Parent / guardian email", type: "email" },
    { name: "emergency_contact", label: "Emergency contact" },
    { name: "phone", label: "Student phone" },
    { name: "email", label: "Student email", type: "email" },
    { name: "parent_ids", label: "Linked parent accounts", type: "multicheck", full: true, options: (parents.data?.items || []).map((p) => ({ value: p.id, label: p.name })) },
    { name: "address", label: "Address", type: "textarea", full: true },
    { name: "previous_school", label: "Previous school", full: true },
  ];
  return { fields, classes, defaults: { academic_year: s?.academic_year, admission_date: todayISO(), status: "active", gender: "Male", parent_ids: [] } };
}

function ImportDialog({ open, onOpenChange, onDone }) {
  const [res, setRes] = useState(null); const [busy, setBusy] = useState(false);
  const pick = async (e) => {
    const f = e.target.files?.[0]; if (!f) return; setBusy(true);
    const fd = new FormData(); fd.append("file", f);
    try { const { data } = await api.post("/students/import", fd); setRes(data); toast.success(`${data.created} students imported`); onDone(); }
    catch (er) { toast.error(errMsg(er)); } finally { setBusy(false); e.target.value = ""; }
  };
  return (
    <Dialog open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) setRes(null); }}>
      <DialogContent data-testid="import-dialog"><DialogHeader><DialogTitle>Import students from CSV</DialogTitle></DialogHeader>
        <p className="text-sm text-muted-foreground">Columns: <code className="text-xs">name, dob (YYYY-MM-DD), gender, class (e.g. Grade 6), section, guardian_name, guardian_phone, guardian_email, address, admission_date, academic_year, blood_group</code></p>
        <label className="flex items-center justify-center gap-2 rounded-lg border-2 border-dashed p-6 cursor-pointer hover:bg-muted/50"><Upload className="h-5 w-5" />{busy ? "Importing…" : "Choose CSV file"}<input type="file" accept=".csv" className="hidden" onChange={pick} data-testid="import-file-input" /></label>
        {res && <div className="text-sm space-y-1" data-testid="import-result"><p className="font-semibold">{res.created} created · {res.errors.length} rows rejected</p>
          <div className="max-h-40 overflow-y-auto text-xs text-rose-600">{res.errors.map((e) => <p key={e.row}>Row {e.row}: {e.error}</p>)}</div></div>}
      </DialogContent>
    </Dialog>
  );
}

function PromoteDialog({ open, onOpenChange, classes }) {
  const fields = [
    { name: "from_class_id", label: "From class", type: "select", required: true, options: classes.map((c) => ({ value: c.id, label: c.name })) },
    { name: "from_section", label: "From section", type: "select", required: true, options: (f) => (classes.find((c) => c.id === f.from_class_id)?.sections || []).map((s) => ({ value: s.name, label: s.name })) },
    { name: "to_class_id", label: "To class", type: "select", required: true, options: classes.map((c) => ({ value: c.id, label: c.name })) },
    { name: "to_section", label: "To section", type: "select", required: true, options: (f) => (classes.find((c) => c.id === f.to_class_id)?.sections || []).map((s) => ({ value: s.name, label: s.name })) },
    { name: "to_academic_year", label: "New academic year", required: true, placeholder: "2027-28" },
  ];
  const submit = async (f) => {
    const { data } = await api.get("/students", { params: { class_id: f.from_class_id, section: f.from_section, status: "active", page_size: 500 } });
    const r = await api.post("/students/promote", { student_ids: data.items.map((s) => s.id), to_class_id: f.to_class_id, to_section: f.to_section, to_academic_year: f.to_academic_year });
    toast.success(`${r.data.promoted} students promoted`);
  };
  return <FormDialog open={open} onOpenChange={onOpenChange} title="Promote students" description="All active students in the source section move to the target class and year. History is preserved." fields={fields} onSubmit={submit} submitLabel="Promote" testid="promote-dialog" />;
}

export function Avatar({ id, name, size = "h-9 w-9" }) {
  return id ? <img src={fileUrl(id)} alt={name} className={`${size} rounded-full object-cover`} /> : <div className={`${size} rounded-full bg-sky-100 dark:bg-sky-500/15 text-sky-700 dark:text-sky-300 grid place-items-center text-sm font-bold`}>{name?.[0]}</div>;
}

export default function Students({ admissions }) {
  const nav = useNavigate(); const { user } = useAuth();
  const { fields, classes, defaults } = useStudentFields();
  const [imp, setImp] = useState(false); const [promo, setPromo] = useState(false); const [k, setK] = useState(0);
  const cols = [
    { key: "name", label: "Student", render: (r) => <div className="flex items-center gap-3"><Avatar id={r.photo_file_id} name={r.name} /><div><p className="font-medium">{r.name}</p><p className="text-xs text-muted-foreground">{r.admission_no}</p></div></div> },
    { key: "class_name", label: "Class", render: (r) => `${r.class_name}-${r.section}` },
    { key: "academic_year", label: "Year" }, { key: "gender", label: "Gender" },
    { key: "guardian_name", label: "Guardian", render: (r) => <span>{r.guardian_name}<span className="block text-xs text-muted-foreground">{r.guardian_phone}</span></span> },
    { key: "status", label: "Status", render: (r) => <Badge value={r.archived ? "archived" : r.status} /> },
  ];
  return (
    <div key={k}>
      <CrudPage title={admissions ? "Admissions" : user.role === "teacher" ? "My Students" : "Students"} subtitle={admissions ? "Register new students. Admission numbers are generated automatically." : "Search, filter and manage student records"}
        endpoint="/students" columns={cols} fields={fields} defaults={defaults} testid="students" exportName="students" searchPlaceholder="Name, admission no, guardian…"
        filters={[{ name: "class_id", label: "Class", options: classes.map((c) => ({ value: c.id, label: c.name })) }, { name: "section", label: "Section", options: ["A", "B", "C", "D"].map((s) => ({ value: s, label: s })) },
          { name: "status", label: "Status", options: ["active", "inactive", "transferred", "graduated"].map((s) => ({ value: s, label: s })) }]}
        rowActions={(r) => <Button variant="ghost" size="sm" onClick={() => nav(`/app/students/${r.id}`)} data-testid={`student-view-${r.id}`}>View</Button>}
        extraActions={user.role === "admin" && <>
          <Button variant="outline" onClick={() => setImp(true)} data-testid="import-students-btn"><Upload className="h-4 w-4 mr-2" />Import CSV</Button>
          <Button variant="outline" onClick={() => setPromo(true)} data-testid="promote-students-btn"><ArrowUpCircle className="h-4 w-4 mr-2" />Promote</Button></>}
        onCreated={(d) => toast.success(`Admission number ${d.admission_no} assigned`)} />
      <ImportDialog open={imp} onOpenChange={setImp} onDone={() => setK(k + 1)} />
      <PromoteDialog open={promo} onOpenChange={(o) => { setPromo(o); if (!o) setK(k + 1); }} classes={classes} />
    </div>
  );
}

function IdCard({ s, school }) {
  return (
    <div className="print-area w-[340px] rounded-2xl overflow-hidden border shadow-lg bg-white text-[#0A192F]" data-testid="student-id-card">
      <div className="bg-[#0A192F] px-4 py-3 text-white"><p className="font-display font-bold text-sm">{school?.school_name}</p><p className="text-[10px] text-amber-300">STUDENT IDENTITY CARD · {s.academic_year}</p></div>
      <div className="p-4 flex gap-4"><Avatar id={s.photo_file_id} name={s.name} size="h-20 w-20" />
        <div className="text-xs space-y-0.5"><p className="font-bold text-base">{s.name}</p><p>Adm. No: <b>{s.admission_no}</b></p><p>Class: {s.class_name}-{s.section}</p><p>DOB: {fdate(s.dob)} · {s.blood_group || "—"}</p><p>Guardian: {s.guardian_phone}</p></div></div>
      <div className="h-1.5 bg-amber-400" />
    </div>
  );
}

export function StudentProfile() {
  const { id } = useParams(); const { user, school } = useAuth();
  const { data: s, loading, error, reload } = useFetch(`/students/${id}`);
  const att = useFetch(`/attendance/student/${id}`);
  const res = useFetch(`/results/student/${id}`);
  const inv = useFetch(user.role !== "teacher" ? "/invoices" : null, { student_id: id, page_size: 50 });
  const [card, setCard] = useState(false); const [login, setLogin] = useState(false); const [tr, setTr] = useState(false);
  const { classes } = useOptions();
  if (loading) return <Loading />; if (error) return <ErrorBox message={error} onRetry={reload} />;
  const info = [["Admission No", s.admission_no], ["Class", `${s.class_name}-${s.section}`], ["Academic year", s.academic_year], ["Date of birth", fdate(s.dob)], ["Gender", s.gender], ["Blood group", s.blood_group],
    ["Admitted", fdate(s.admission_date)], ["Guardian", s.guardian_name], ["Guardian phone", s.guardian_phone], ["Guardian email", s.guardian_email], ["Emergency", s.emergency_contact], ["Address", s.address], ["Previous school", s.previous_school], ["Transport", s.transport ? `${s.transport.route_name} · ${s.transport.stop}` : "Not assigned"]];
  return (
    <div className="page" data-testid="student-profile">
      <Link to="/app/students" className="inline-flex items-center gap-1 text-sm text-muted-foreground no-print"><ArrowLeft className="h-4 w-4" />Students</Link>
      <PageHeader title={<span className="flex items-center gap-3"><Avatar id={s.photo_file_id} name={s.name} size="h-12 w-12" />{s.name} <Badge value={s.status} /></span>} subtitle={`${s.admission_no} · ${s.class_name}-${s.section}`}
        actions={<><Button variant="outline" onClick={() => setCard(true)} data-testid="id-card-btn"><IdIcon className="h-4 w-4 mr-2" />ID card</Button><Button variant="outline" onClick={() => window.print()} data-testid="print-profile-btn"><Printer className="h-4 w-4 mr-2" />Print</Button>
          {user.role === "admin" && <><Button variant="outline" onClick={() => setTr(true)} data-testid="transfer-btn">Transfer section</Button><Button variant="outline" onClick={() => setLogin(true)} data-testid="create-login-btn"><KeyRound className="h-4 w-4 mr-2" />Create login</Button></>}</>} />
      <div className="print-area">
        <Tabs defaultValue="profile">
          <TabsList className="no-print"><TabsTrigger value="profile">Profile</TabsTrigger><TabsTrigger value="attendance" data-testid="tab-attendance">Attendance</TabsTrigger><TabsTrigger value="results" data-testid="tab-results">Results</TabsTrigger>{inv.data && <TabsTrigger value="fees" data-testid="tab-fees">Fees</TabsTrigger>}<TabsTrigger value="history">History</TabsTrigger></TabsList>
          <TabsContent value="profile"><Section><dl className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">{info.map(([k, v]) => <div key={k}><dt className="text-xs uppercase tracking-wider text-muted-foreground">{k}</dt><dd className="text-sm font-medium mt-0.5">{v || "—"}</dd></div>)}</dl></Section></TabsContent>
          <TabsContent value="attendance"><Section title={`Attendance: ${att.data?.percentage ?? "—"}%`}>{att.data && <><div className="flex gap-3 mb-4 flex-wrap">{Object.entries(att.data.counts).map(([k, v]) => <Badge key={k} value={k} label={`${k}: ${v}`} />)}</div>
            <div className="grid grid-cols-7 sm:grid-cols-10 gap-1">{att.data.records.slice(0, 60).map((r) => <div key={r.date} title={`${r.date}: ${r.status}`} className={`rounded p-1 text-center text-[10px] ${r.status === "present" ? "bg-emerald-100 text-emerald-800" : r.status === "absent" ? "bg-rose-100 text-rose-800" : r.status === "late" ? "bg-amber-100 text-amber-800" : "bg-sky-100 text-sky-800"}`}>{r.date.slice(5)}</div>)}</div></>}</Section></TabsContent>
          <TabsContent value="results"><Section>{(res.data || []).map((r) => <div key={r.exam_id} className="flex items-center justify-between border-b py-2 text-sm"><span>{r.name} <span className="text-xs text-muted-foreground">({r.term})</span></span><span className="flex items-center gap-3">{r.percentage}% · {r.grade}<Badge value={r.result} /><Link to={`/app/report-card/${r.exam_id}/${id}`} className="text-sky-600 text-xs">Report card</Link></span></div>)}</Section></TabsContent>
          {inv.data && <TabsContent value="fees"><Section>{inv.data.items.map((i) => <div key={i.id} className="flex justify-between border-b py-2 text-sm"><span>{i.invoice_no} · {i.items.map((x) => x.name).join(", ")}</span><span className="flex gap-3">{inr(i.total)} · bal {inr(i.balance)}<Badge value={i.display_status} /></span></div>)}</Section></TabsContent>}
          <TabsContent value="history"><Section>{(s.history || []).map((h, i) => <div key={i} className="border-l-2 border-amber-400 pl-4 pb-3 text-sm"><p className="font-medium capitalize">{h.event.replace(/_/g, " ")}</p><p className="text-xs text-muted-foreground">{fdate(h.date)} · {h.class_name}-{h.section} · {h.academic_year}{h.from ? ` · from ${h.from}` : ""}</p></div>)}</Section></TabsContent>
        </Tabs>
      </div>
      <Dialog open={card} onOpenChange={setCard}><DialogContent className="w-auto"><DialogHeader><DialogTitle>Student ID card</DialogTitle></DialogHeader><IdCard s={s} school={school} /><Button onClick={() => window.print()} data-testid="print-id-card-btn"><Printer className="h-4 w-4 mr-2" />Print ID card</Button></DialogContent></Dialog>
      <FormDialog open={login} onOpenChange={setLogin} title="Create student login" fields={[{ name: "email", label: "Login email", type: "email", required: true }, { name: "password", label: "Temporary password", type: "password", required: true, help: "Min 8 characters with letters and numbers" }]}
        initial={{ email: s.email || "" }} onSubmit={async (f) => { await api.post(`/students/${id}/create-login`, f); toast.success("Login created"); }} testid="create-login-dialog" />
      <FormDialog open={tr} onOpenChange={setTr} title="Transfer to another section" fields={[{ name: "section", label: "New section", type: "select", required: true, options: (classes.find((c) => c.id === s.class_id)?.sections || []).filter((x) => x.name !== s.section).map((x) => ({ value: x.name, label: x.name })) }]}
        onSubmit={async (f) => { await api.post(`/students/${id}/transfer`, f); toast.success("Transferred"); reload(); }} testid="transfer-dialog" />
    </div>
  );
}
