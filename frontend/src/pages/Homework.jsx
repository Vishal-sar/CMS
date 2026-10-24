import { useState } from "react";
import { Plus, Paperclip, Send } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { FormDialog, FileField } from "@/components/app/FormDialog";
import { DataTable } from "@/components/app/DataTable";
import { useFetch, useOptions, PageHeader, Section, Badge, Loading, Empty, Confirm } from "@/components/app/common";
import { api, errMsg, fileUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fdate, todayISO } from "@/lib/fmt";

const Files = ({ files }) => (files || []).length ? <div className="flex flex-wrap gap-2 mt-2">{files.map((f) => <a key={f.id} href={fileUrl(f.id)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 rounded-md bg-secondary px-2 py-1 text-xs hover:underline"><Paperclip className="h-3 w-3" />{f.name || "Attachment"}</a>)}</div> : null;

function Submissions({ hw, onClose }) {
  const { data, reload } = useFetch(hw ? `/homework/${hw.id}/submissions` : null); const [g, setG] = useState(null);
  return (
    <Dialog open={!!hw} onOpenChange={(o) => !o && onClose()}><DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="submissions-dialog">
      <DialogHeader><DialogTitle>{hw?.title} — submissions</DialogTitle></DialogHeader>
      {!data ? <Loading /> : <div className="divide-y">{data.students.map((s, i) => (
        <div key={s.id} className="py-3 text-sm" data-testid={`submission-row-${i}`}>
          <div className="flex justify-between gap-2"><span><b>{s.name}</b> <span className="text-xs text-muted-foreground">{s.admission_no}</span></span>
            {s.submission ? <span className="flex items-center gap-2">{s.submission.late && <Badge value="late" />}<Badge value={s.submission.status} />{s.submission.grade != null && <b>{s.submission.grade}/{data.homework.max_score}</b>}
              <Button size="sm" variant="outline" onClick={() => setG(s.submission)} data-testid={`grade-btn-${i}`}>Grade</Button></span> : <Badge value={hw.overdue ? "overdue" : "pending"} label="Not submitted" />}</div>
          {s.submission?.text && <p className="text-xs text-muted-foreground mt-1 whitespace-pre-wrap">{s.submission.text}</p>}<Files files={s.submission?.files} />
          {s.submission?.feedback && <p className="text-xs mt-1">Feedback: {s.submission.feedback}</p>}</div>))}</div>}
      <FormDialog open={!!g} onOpenChange={(o) => !o && setG(null)} title="Grade submission" initial={{ grade: g?.grade ?? "", feedback: g?.feedback || "" }} testid="grade-form"
        fields={[{ name: "grade", label: `Score (out of ${hw?.max_score})`, type: "number", required: true, validate: (v) => (v < 0 || v > hw?.max_score ? `0–${hw?.max_score}` : null) }, { name: "feedback", label: "Feedback", type: "textarea" }]}
        onSubmit={async (f) => { await api.put(`/submissions/${g.id}/grade`, f); toast.success("Graded"); reload(); }} />
    </DialogContent></Dialog>
  );
}

function SubmitBox({ h, onDone }) {
  const [text, setText] = useState(h.my_submission?.text || ""); const [files, setFiles] = useState(h.my_submission?.files || []); const [busy, setBusy] = useState(false);
  const go = async () => { setBusy(true); try { const { data } = await api.post(`/homework/${h.id}/submit`, { text, files }); toast.success(data.late ? "Submitted (late)" : "Submitted"); onDone(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); } };
  if (h.my_submission?.grade != null) return null;
  return (<div className="mt-3 space-y-2 border-t pt-3"><Textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="Type your answer…" rows={3} data-testid={`submit-text-${h.id}`} />
    <FileField value={files} onChange={setFiles} context="submission" accept=".pdf,.jpg,.jpeg,.png,.doc,.docx,.txt" multiple testid={`submit-file-${h.id}`} />
    <Button size="sm" onClick={go} disabled={busy} data-testid={`submit-hw-${h.id}`}><Send className="h-4 w-4 mr-1" />{h.my_submission ? "Resubmit" : "Submit"}</Button></div>);
}

export default function Homework() {
  const { user, childId } = useAuth(); const { classes, subjects } = useOptions(); const staff = user.role === "admin" || user.role === "teacher";
  const asg = useFetch(user.role === "teacher" ? "/assignments" : null);
  const { data, loading, reload } = useFetch("/homework", { page_size: 100, student_id: user.role === "parent" ? childId : undefined }, [childId]);
  const [edit, setEdit] = useState(null); const [subs, setSubs] = useState(null);
  const pairs = user.role === "teacher" ? (asg.data || []) : classes.flatMap((c) => c.sections.flatMap((s) => subjects.map((j) => ({ class_id: c.id, class_name: c.name, section: s.name, subject_id: j.id, subject_name: j.name }))));
  const fields = [{ name: "title", label: "Title", required: true, full: true },
    { name: "target", label: "Class · section · subject", type: "select", required: true, full: true, options: pairs.map((p) => ({ value: `${p.class_id}|${p.section}|${p.subject_id}`, label: `${p.class_name}-${p.section} · ${p.subject_name}` })) },
    { name: "due_date", label: "Due date", type: "date", required: true }, { name: "max_score", label: "Max score", type: "number" },
    { name: "description", label: "Description", type: "textarea", full: true }, { name: "instructions", label: "Instructions", type: "textarea", full: true },
    { name: "attachments", label: "Attachments", type: "file", multiple: true, context: "homework", accept: ".pdf,.jpg,.jpeg,.png,.doc,.docx,.txt", full: true },
    { name: "status", label: "Status", type: "select", options: ["draft", "published", "archived"].map((v) => ({ value: v, label: v })) }];
  const save = async (f) => { const [class_id, section, subject_id] = f.target.split("|"); const b = { title: f.title, class_id, section, subject_id, due_date: f.due_date, max_score: f.max_score || 10, description: f.description || "", instructions: f.instructions || "", attachments: f.attachments || [], status: f.status };
    if (f.id) await api.put(`/homework-items/${f.id}`, b); else await api.post("/homework-items", b); toast.success("Homework saved"); reload(); };
  return (
    <div className="page" data-testid="homework-page">
      <PageHeader title="Homework & Assignments" subtitle={staff ? "Create assignments, review submissions and give feedback" : "Assignments, deadlines and feedback"}
        actions={staff && <Button onClick={() => setEdit({ due_date: todayISO(), status: "published", max_score: 10, attachments: [] })} data-testid="add-homework-btn"><Plus className="h-4 w-4 mr-2" />New assignment</Button>} />
      {loading && !data ? <Loading /> : !data?.items.length ? <Empty title="No homework" /> : staff ?
        <Section><DataTable rows={data.items} testid="homework-table" columns={[{ key: "title", label: "Assignment", render: (r) => <span><b>{r.title}</b><span className="block text-xs text-muted-foreground">{r.class_name}-{r.section} · {r.subject_name}</span></span> },
          { key: "due_date", label: "Due", render: (r) => <span className={r.overdue ? "text-rose-600" : ""}>{fdate(r.due_date)}</span> }, { key: "status", label: "Status", render: (r) => <Badge value={r.status} /> }, { key: "submission_count", label: "Submissions" },
          { key: "a", label: "", className: "text-right", render: (r) => <div className="flex justify-end gap-1"><Button size="sm" variant="outline" onClick={() => setSubs(r)} data-testid={`view-subs-${r.id}`}>Submissions</Button>
            <Button size="sm" variant="ghost" onClick={() => setEdit({ ...r, target: `${r.class_id}|${r.section}|${r.subject_id}` })} data-testid={`edit-hw-${r.id}`}>Edit</Button>
            <Confirm title="Archive this assignment?" onConfirm={() => api.delete(`/homework-items/${r.id}`).then(() => { toast.success("Archived"); reload(); })} trigger={<Button size="sm" variant="ghost" data-testid={`archive-hw-${r.id}`}>Archive</Button>} /></div> }]} /></Section>
        : <div className="grid md:grid-cols-2 gap-4">{data.items.map((h) => (
          <Section key={h.id} testid={`hw-card-${h.id}`} title={<span>{h.title}<span className="block text-xs font-normal text-muted-foreground">{h.subject_name} · due {fdate(h.due_date)}{h.student_name && user.role === "parent" ? ` · ${h.student_name}` : ""}</span></span>}
            action={h.my_submission ? <Badge value={h.my_submission.status} /> : <Badge value={h.overdue ? "overdue" : "pending"} />}>
            <p className="text-sm whitespace-pre-wrap">{h.description}</p>{h.instructions && <p className="text-xs text-muted-foreground mt-2">{h.instructions}</p>}<Files files={h.attachments} />
            {h.my_submission?.grade != null && <p className="mt-3 text-sm rounded-lg bg-emerald-50 dark:bg-emerald-500/10 p-2">Score <b>{h.my_submission.grade}/{h.max_score}</b>{h.my_submission.feedback && ` · ${h.my_submission.feedback}`}</p>}
            {user.role === "student" && <SubmitBox h={h} onDone={reload} />}</Section>))}</div>}
      <FormDialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)} wide title={edit?.id ? "Edit assignment" : "New assignment"} fields={fields} initial={edit} onSubmit={save} testid="homework-form" />
      <Submissions hw={subs} onClose={() => { setSubs(null); reload(); }} />
    </div>
  );
}
