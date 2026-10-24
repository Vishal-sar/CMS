import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Plus, Trash2, Printer, Send, Eye, EyeOff, ArrowLeft } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { FormDialog, SelectField } from "@/components/app/FormDialog";
import { DataTable } from "@/components/app/DataTable";
import { useFetch, useOptions, PageHeader, Section, Badge, Loading, Empty, ErrorBox, Confirm } from "@/components/app/common";
import { api, errMsg, fileUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fdate } from "@/lib/fmt";
import { SaveBar } from "./Academic";

function SubjectRows({ value, set, subjects }) {
  const arr = value || []; const upd = (i, k, v) => set(arr.map((s, j) => (j === i ? { ...s, [k]: v } : s)));
  return (<div className="space-y-2">{arr.map((s, i) => (
    <div key={i} className="grid grid-cols-12 gap-2 items-center">
      <div className="col-span-4"><SelectField value={s.subject_id} onChange={(v) => upd(i, "subject_id", v)} options={subjects.map((x) => ({ value: x.id, label: x.name }))} testid={`exam-subj-${i}`} /></div>
      <input type="date" className="col-span-3 h-9 rounded-md border px-2 text-xs bg-background" value={s.date || ""} onChange={(e) => upd(i, "date", e.target.value)} data-testid={`exam-date-${i}`} />
      <input type="number" className="col-span-2 h-9 rounded-md border px-2 text-sm bg-background" value={s.max_marks} onChange={(e) => upd(i, "max_marks", Number(e.target.value))} title="Max marks" />
      <input type="number" className="col-span-2 h-9 rounded-md border px-2 text-sm bg-background" value={s.pass_marks} onChange={(e) => upd(i, "pass_marks", Number(e.target.value))} title="Pass marks" />
      <button type="button" onClick={() => set(arr.filter((_, j) => j !== i))} aria-label="Remove"><Trash2 className="h-4 w-4 text-rose-500" /></button></div>))}
    <p className="text-[11px] text-muted-foreground">Subject · date · max marks · passing marks</p>
    <Button type="button" size="sm" variant="outline" onClick={() => set([...arr, { subject_id: "", date: "", max_marks: 100, pass_marks: 35 }])} data-testid="add-exam-subject"><Plus className="h-4 w-4 mr-1" />Add subject</Button></div>);
}

export default function Exams() {
  const { user } = useAuth(); const { classes, subjects } = useOptions(); const { data: st } = useFetch("/settings");
  const [cls, setCls] = useState(""); const { data, loading, error, reload } = useFetch("/exams", { class_id: cls }); const [edit, setEdit] = useState(null);
  const fields = [{ name: "name", label: "Exam name", required: true }, { name: "type", label: "Type", type: "select", required: true, options: ["Unit Test", "Mid-Term", "Final Examination", "Practical", "Other"].map((v) => ({ value: v, label: v })) },
    { name: "academic_year", label: "Academic year", required: true }, { name: "term", label: "Term", type: "select", required: true, options: (st?.terms || ["Term 1", "Term 2"]).map((t) => ({ value: t, label: t })) },
    { name: "class_id", label: "Class", type: "select", required: true, options: classes.map((c) => ({ value: c.id, label: c.name })), onChange: () => ({ sections: [] }) },
    { name: "sections", label: "Sections", type: "multicheck", required: true, options: (f) => (classes.find((c) => c.id === f.class_id)?.sections || []).map((s) => ({ value: s.name, label: s.name })) },
    { name: "weight", label: "Weight in final result (%)", type: "number", min: 0, max: 100 },
    { name: "subjects", label: "Subjects & schedule", type: "custom", full: true, render: (p) => <SubjectRows {...p} subjects={subjects} />, validate: (v) => (!v?.length || v.some((x) => !x.subject_id || !x.date) ? "Each subject needs a subject and date" : v.some((x) => x.pass_marks > x.max_marks) ? "Pass marks exceed max marks" : null) }];
  const pub = async (e, p) => { try { await api.post(`/exams/${e.id}/publish`, null, { params: { publish: p } }); toast.success(p ? "Results published; students and parents notified" : "Unpublished"); reload(); } catch (er) { toast.error(errMsg(er)); } };
  const cols = [{ key: "name", label: "Exam", render: (r) => <span><b>{r.name}</b><span className="block text-xs text-muted-foreground">{r.type} · {r.term} · {r.academic_year}</span></span> },
    { key: "class_name", label: "Class", render: (r) => `${r.class_name} (${r.sections.join(", ")})` }, { key: "subjects", label: "Dates", render: (r) => r.subjects.length ? `${fdate(r.subjects.map((s) => s.date).sort()[0])} – ${fdate(r.subjects.map((s) => s.date).sort().slice(-1)[0])}` : "—" },
    { key: "status", label: "Status", render: (r) => <Badge value={r.status} /> },
    { key: "a", label: "", className: "text-right", render: (r) => <div className="flex justify-end gap-1">
      <Link to={`/app/results?exam=${r.id}`}><Button size="sm" variant="ghost" data-testid={`exam-results-${r.id}`}>Marks & results</Button></Link>
      {user.role === "admin" && <>{r.status === "draft" && <Button size="sm" variant="ghost" onClick={() => setEdit(r)} data-testid={`exam-edit-${r.id}`}>Edit</Button>}
        <Confirm title={r.status === "published" ? "Unpublish results?" : "Publish results?"} description={r.status === "published" ? "Students and parents will no longer see these results." : "Students and parents will be able to view results and report cards."} destructive={false}
          onConfirm={() => pub(r, r.status !== "published")} trigger={<Button size="sm" variant="outline" data-testid={`exam-publish-${r.id}`}>{r.status === "published" ? <><EyeOff className="h-4 w-4 mr-1" />Unpublish</> : <><Eye className="h-4 w-4 mr-1" />Publish</>}</Button>} /></>}</div> }];
  return (
    <div className="page" data-testid="exams-page">
      <PageHeader title="Examinations" subtitle="Set up exams, schedules, maximum and passing marks" actions={user.role === "admin" && <Button onClick={() => setEdit({ academic_year: st?.academic_year, term: "Term 1", type: "Unit Test", weight: 100, sections: [], subjects: [] })} data-testid="create-exam-btn"><Plus className="h-4 w-4 mr-2" />Create exam</Button>} />
      <Section><div className="w-52 mb-4"><SelectField value={cls} onChange={setCls} allowEmpty="All classes" options={classes.map((c) => ({ value: c.id, label: c.name }))} testid="exam-class-filter" /></div>
        <DataTable columns={cols} rows={data?.items} loading={loading} error={error} onRetry={reload} testid="exams-table" empty={<Empty title="No exams yet" />} /></Section>
      <FormDialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)} wide title={edit?.id ? "Edit exam" : "Create exam"} fields={fields} initial={edit} testid="exam-form"
        onSubmit={async (f) => { const b = { name: f.name, type: f.type, academic_year: f.academic_year, term: f.term, class_id: f.class_id, sections: f.sections, subjects: f.subjects, weight: f.weight ?? 100 }; if (f.id) await api.put(`/exams/${f.id}`, b); else await api.post("/exams", b); toast.success("Exam saved"); reload(); }} />
    </div>
  );
}

function MarksEntry({ exam }) {
  const { user } = useAuth(); const asg = useFetch(user.role === "teacher" ? "/assignments" : null);
  const [sec, setSec] = useState(""); const [sub, setSub] = useState(""); const [d, setD] = useState(null); const [busy, setBusy] = useState(false);
  const allowed = (s, j) => user.role === "admin" || (asg.data || []).some((a) => a.class_id === exam.class_id && a.section === s && a.subject_id === j);
  useEffect(() => { if (!sec || !sub) return; setD(null); api.get(`/exams/${exam.id}/marks`, { params: { section: sec, subject_id: sub } }).then((r) => setD(r.data)).catch((e) => { toast.error(errMsg(e)); setD(false); }); }, [sec, sub, exam.id]);
  const save = async (submit) => {
    const bad = d.students.find((s) => !s.absent && s.marks !== null && s.marks !== "" && (s.marks < 0 || s.marks > d.max_marks));
    if (bad) { toast.error(`${bad.name}: marks must be 0–${d.max_marks}`); return; }
    setBusy(true);
    try { await api.post(`/exams/${exam.id}/marks`, { section: sec, subject_id: sub, submit, entries: d.students.map((s) => ({ student_id: s.id, marks: s.marks === "" ? null : s.marks, absent: s.absent })) }); toast.success(submit ? "Marks submitted" : "Draft saved"); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const upd = (id, k, v) => setD({ ...d, students: d.students.map((s) => (s.id === id ? { ...s, [k]: v } : s)) });
  return (<div className="space-y-4">
    <Section><div className="flex flex-wrap gap-3">
      <div className="w-32"><SelectField value={sec} onChange={setSec} placeholder="Section" options={exam.sections.map((s) => ({ value: s, label: `Section ${s}` }))} testid="marks-section" /></div>
      <div className="w-56"><SelectField value={sub} onChange={setSub} placeholder="Subject" options={exam.subjects.filter((s) => !sec || allowed(sec, s.subject_id)).map((s) => ({ value: s.subject_id, label: s.subject_name }))} testid="marks-subject" /></div>
      {d && <span className="text-sm text-muted-foreground self-center">Max {d.max_marks} · Pass {d.pass_marks} {exam.status === "published" && "· Published: corrections are logged"}</span>}</div></Section>
    {!sec || !sub ? <Empty title="Choose a section and subject" /> : d === null ? <Loading /> : d === false ? <ErrorBox message="You cannot enter marks for this subject" /> : <>
      <Section><div className="divide-y">{d.students.map((s, i) => (
        <div key={s.id} className="flex items-center gap-3 py-2" data-testid={`marks-row-${i}`}>
          <div className="flex-1"><p className="text-sm font-medium">{s.name}</p><p className="text-xs text-muted-foreground">{s.admission_no} {s.mark_status && `· ${s.mark_status}`}</p></div>
          <Input type="number" min={0} max={d.max_marks} disabled={s.absent} value={s.marks ?? ""} onChange={(e) => upd(s.id, "marks", e.target.value === "" ? "" : Number(e.target.value))}
            className={`w-24 ${s.marks > d.max_marks || s.marks < 0 ? "border-rose-500" : ""}`} data-testid={`marks-input-${i}`} />
          <label className="flex items-center gap-1.5 text-xs"><Checkbox checked={s.absent} onCheckedChange={(v) => upd(s.id, "absent", !!v)} data-testid={`marks-absent-${i}`} />Absent</label></div>))}</div></Section>
      <SaveBar onSave={() => save(true)} busy={busy} label="Submit marks" extra={<Button variant="outline" onClick={() => save(false)} disabled={busy} data-testid="save-draft-marks">Save draft</Button>} /></>}
  </div>);
}

function ExamResults({ exam }) {
  const [sec, setSec] = useState(""); const { data, loading } = useFetch(`/exams/${exam.id}/results`, { section: sec });
  return (<div className="space-y-4">
    <Section><div className="w-40"><SelectField value={sec} onChange={setSec} allowEmpty="All sections" options={exam.sections.map((s) => ({ value: s, label: s }))} testid="results-section" /></div></Section>
    {data && <div className="grid sm:grid-cols-3 lg:grid-cols-6 gap-3">{data.subject_stats.map((s) => <div key={s.subject_name} className="card-surface p-3 text-xs"><p className="font-semibold text-sm">{s.subject_name}</p><p>Avg {s.average}/{s.max_marks}</p><p>High {s.highest} · Pass {s.pass_rate}%</p></div>)}</div>}
    <Section><DataTable loading={loading} rows={data?.results} testid="results-table" columns={[{ key: "rank", label: "#" },
      { key: "name", label: "Student", render: (r) => <span>{r.name}<span className="block text-xs text-muted-foreground">{r.admission_no} · {r.section}</span></span> },
      { key: "total", label: "Total", render: (r) => `${r.total}/${r.max_total}` }, { key: "percentage", label: "%" }, { key: "grade", label: "Grade" }, { key: "result", label: "Result", render: (r) => <Badge value={r.result} /> },
      { key: "rc", label: "", render: (r) => <Link to={`/app/report-card/${exam.id}/${r.id}`} className="text-sky-600 text-xs" data-testid={`report-card-link-${r.id}`}>Report card</Link> }]} /></Section></div>);
}

function MyResults() {
  const { user, childId } = useAuth(); const sid = user.role === "student" ? user.profile_id : childId;
  const { data, loading } = useFetch(sid ? `/results/student/${sid}` : null);
  if (loading || !data) return <Loading />;
  if (!data.length) return <Empty title="No published results yet" />;
  return <div className="space-y-4">{data.map((r) => (
    <Section key={r.exam_id} title={<span>{r.name} <span className="text-xs text-muted-foreground font-normal">{r.term}</span></span>} action={<Link to={`/app/report-card/${r.exam_id}/${sid}`}><Button size="sm" variant="outline" data-testid={`view-report-${r.exam_id}`}>Report card</Button></Link>}>
      <div className="flex gap-6 mb-3 text-sm"><span>Total <b>{r.total}/{r.max_total}</b></span><span><b>{r.percentage}%</b></span><span>Grade <b>{r.grade}</b></span><Badge value={r.result} /></div>
      <DataTable rows={r.subjects} rowKey="subject_id" testid={`my-results-${r.exam_id}`} columns={[{ key: "subject_name", label: "Subject" }, { key: "marks", label: "Marks", render: (x) => (x.absent ? "AB" : x.marks ?? "—") }, { key: "max_marks", label: "Max" }, { key: "grade", label: "Grade" }, { key: "passed", label: "", render: (x) => <Badge value={x.passed ? "pass" : "fail"} /> }]} />
    </Section>))}</div>;
}

export function Results() {
  const { user } = useAuth(); const params = new URLSearchParams(window.location.search);
  const exams = useFetch(user.role === "admin" || user.role === "teacher" ? "/exams" : null, { page_size: 100 });
  const [eid, setEid] = useState(params.get("exam") || ""); const [tab, setTab] = useState("marks");
  const exam = (exams.data?.items || []).find((e) => e.id === eid);
  if (user.role === "student" || user.role === "parent") return <div className="page"><PageHeader title="Results" subtitle="Published examination results" /><MyResults /></div>;
  return (
    <div className="page" data-testid="results-page">
      <PageHeader title="Marks & Results" subtitle="Enter marks, review results and print report cards" />
      <Section><div className="flex flex-wrap gap-3"><div className="w-80"><SelectField value={eid} onChange={setEid} placeholder="Choose an exam" options={(exams.data?.items || []).map((e) => ({ value: e.id, label: `${e.name} · ${e.class_name} (${e.status})` }))} testid="results-exam-select" /></div>
        <div className="flex rounded-lg border p-1">{["marks", "results"].map((t) => <button key={t} onClick={() => setTab(t)} className={`px-3 py-1 text-sm rounded-md capitalize ${tab === t ? "bg-primary text-primary-foreground" : ""}`} data-testid={`results-tab-${t}`}>{t === "marks" ? "Marks entry" : "Results"}</button>)}</div></div></Section>
      {!exam ? <Empty title="Select an exam" /> : tab === "marks" ? <MarksEntry exam={exam} key={exam.id} /> : <ExamResults exam={exam} key={exam.id} />}
    </div>
  );
}

export function ReportCard() {
  const { eid, sid } = useParams(); const { user } = useAuth();
  const { data: r, loading, error, reload } = useFetch(`/report-card/${eid}/${sid}`); const [rem, setRem] = useState(null);
  if (loading) return <Loading />; if (error) return <div className="page"><ErrorBox message={error} /></div>;
  const saveRem = async () => { try { await api.put(`/exams/${eid}/remarks`, { student_id: sid, remark: rem }); toast.success("Remark saved"); setRem(null); reload(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <div className="page">
      <div className="flex justify-between no-print"><button onClick={() => window.history.back()} className="inline-flex items-center gap-1 text-sm text-muted-foreground"><ArrowLeft className="h-4 w-4" />Back</button>
        <div className="flex gap-2">{(user.role === "admin" || user.role === "teacher") && <Button variant="outline" onClick={() => setRem(r.remark || "")} data-testid="edit-remark-btn">Edit remark</Button>}<Button onClick={() => window.print()} data-testid="print-report-card-btn"><Printer className="h-4 w-4 mr-2" />Print</Button></div></div>
      {rem !== null && <Section className="no-print"><textarea className="w-full rounded-md border p-2 text-sm bg-background" rows={3} value={rem} onChange={(e) => setRem(e.target.value)} data-testid="remark-input" /><Button size="sm" className="mt-2" onClick={saveRem} data-testid="save-remark-btn"><Send className="h-4 w-4 mr-1" />Save</Button></Section>}
      <div className="print-area bg-white text-[#0A192F] rounded-xl border shadow-sm max-w-3xl mx-auto p-8" data-testid="report-card">
        <div className="flex items-center gap-4 border-b-4 border-amber-400 pb-4">
          {r.school.logo_file_id && <img src={fileUrl(r.school.logo_file_id)} alt="logo" className="h-16 w-16 object-contain" />}
          <div className="flex-1"><h2 className="text-2xl font-bold">{r.school.school_name}</h2><p className="text-xs">{r.school.address} · {r.school.phone}</p></div>
          <div className="text-right"><p className="text-xs uppercase tracking-widest text-sky-700 font-bold">Report Card</p><p className="text-sm font-semibold">{r.exam.name}</p><p className="text-xs">{r.exam.term} · {r.exam.academic_year}</p></div></div>
        <div className="grid grid-cols-2 gap-2 text-sm my-5"><p>Name: <b>{r.student.name}</b></p><p>Admission No: <b>{r.student.admission_no}</b></p><p>Class: <b>{r.student.class_name}-{r.student.section}</b></p><p>Date of birth: {fdate(r.student.dob)}</p></div>
        <table className="w-full text-sm border"><thead className="bg-[#0A192F] text-white"><tr>{["Subject", "Max", "Pass", "Obtained", "Grade", "Status"].map((h) => <th key={h} className="p-2 text-left">{h}</th>)}</tr></thead>
          <tbody>{r.subjects.map((s) => <tr key={s.subject_id} className="border-t"><td className="p-2">{s.subject_name}</td><td className="p-2">{s.max_marks}</td><td className="p-2">{s.pass_marks}</td><td className="p-2 font-semibold">{s.absent ? "AB" : s.marks ?? "—"}</td><td className="p-2">{s.grade}</td><td className="p-2">{s.passed ? "Pass" : "Fail"}</td></tr>)}
            <tr className="border-t bg-slate-50 font-bold"><td className="p-2">Total</td><td className="p-2">{r.max_total}</td><td /><td className="p-2">{r.total}</td><td className="p-2">{r.grade}</td><td className="p-2">{r.result}</td></tr></tbody></table>
        <div className="grid grid-cols-3 gap-4 my-5 text-sm"><div className="rounded-lg bg-sky-50 p-3"><p className="text-xs">Percentage</p><p className="text-xl font-bold">{r.percentage}%</p></div><div className="rounded-lg bg-amber-50 p-3"><p className="text-xs">Overall grade</p><p className="text-xl font-bold">{r.grade}</p></div>
          <div className="rounded-lg bg-emerald-50 p-3"><p className="text-xs">Attendance</p><p className="text-xl font-bold">{r.attendance.percentage ?? "—"}%</p><p className="text-[10px]">P {r.attendance.present} · L {r.attendance.late} · A {r.attendance.absent}</p></div></div>
        <p className="text-sm"><b>Teacher's remarks:</b> {r.remark || "—"}</p>
        <div className="grid grid-cols-3 gap-6 mt-14 text-xs text-center">{[`Class Teacher${r.class_teacher ? ` (${r.class_teacher})` : ""}`, "Principal", "Parent / Guardian"].map((x) => <div key={x} className="border-t pt-2">{x}</div>)}</div>
      </div>
    </div>
  );
}
