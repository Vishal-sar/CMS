import { useState } from "react";
import { Plus, Trash2, Save, Printer } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import CrudPage from "@/components/app/CrudPage";
import { FormDialog, SelectField } from "@/components/app/FormDialog";
import { DataTable } from "@/components/app/DataTable";
import { useFetch, useOptions, PageHeader, Section, Confirm, Badge, Loading, Empty } from "@/components/app/common";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fdate } from "@/lib/fmt";

function Assignments() {
  const { classes, subjects } = useOptions(); const teachers = useFetch("/teachers", { page_size: 500, sort: "name" });
  const [cls, setCls] = useState(""); const { data, reload, loading } = useFetch("/assignments", { class_id: cls }); const [o, setO] = useState(false);
  const fields = [{ name: "class_id", label: "Class", type: "select", required: true, options: classes.map((c) => ({ value: c.id, label: c.name })) },
    { name: "section", label: "Section", type: "select", required: true, options: (f) => (classes.find((c) => c.id === f.class_id)?.sections || []).map((s) => ({ value: s.name, label: s.name })) },
    { name: "subject_id", label: "Subject", type: "select", required: true, options: subjects.map((s) => ({ value: s.id, label: s.name })) },
    { name: "teacher_id", label: "Teacher", type: "select", required: true, options: (teachers.data?.items || []).map((t) => ({ value: t.id, label: `${t.name} (${t.specialization || t.department})` })) }];
  const del = async (a) => { try { await api.delete(`/assignments/${a.id}`); toast.success("Removed"); reload(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <Section title="Teacher · subject · section assignments" action={<div className="flex gap-2"><div className="w-44"><SelectField value={cls} onChange={setCls} allowEmpty="All classes" options={classes.map((c) => ({ value: c.id, label: c.name }))} testid="assign-class-filter" /></div>
      <Button onClick={() => setO(true)} data-testid="add-assignment-btn"><Plus className="h-4 w-4 mr-1" />Assign</Button></div>}>
      <DataTable loading={loading} rows={(data || []).sort((a, b) => `${a.class_name}${a.section}`.localeCompare(`${b.class_name}${b.section}`))} testid="assignments-table" columns={[
        { key: "class_name", label: "Class", render: (r) => `${r.class_name}-${r.section}` }, { key: "subject_name", label: "Subject" }, { key: "teacher_name", label: "Teacher" },
        { key: "x", label: "", className: "text-right", render: (r) => <Confirm title="Remove this assignment?" description="History is kept." onConfirm={() => del(r)} trigger={<Button variant="ghost" size="icon" aria-label="Remove" data-testid={`del-assign-${r.id}`}><Trash2 className="h-4 w-4" /></Button>} /> }]} />
      <FormDialog open={o} onOpenChange={setO} title="Assign teacher" fields={fields} onSubmit={async (f) => { await api.post("/assignments", f); toast.success("Assigned"); reload(); }} testid="assignment-form" />
    </Section>
  );
}

export function Subjects() {
  const { user } = useAuth(); const { classes } = useOptions();
  if (user.role === "teacher") return <MySubjects />;
  const fields = [{ name: "name", label: "Subject name", required: true }, { name: "code", label: "Code", required: true }, { name: "type", label: "Type", type: "select", options: ["Theory", "Practical", "Theory + Practical", "Activity"].map((v) => ({ value: v, label: v })) },
    { name: "class_ids", label: "Taught in classes", type: "multicheck", full: true, options: classes.map((c) => ({ value: c.id, label: c.name })) }];
  const cn = Object.fromEntries(classes.map((c) => [c.id, c.name]));
  return (
    <div className="page">
      <PageHeader title="Subjects" subtitle="Subjects per class and teacher assignments" />
      <Tabs defaultValue="subjects"><TabsList><TabsTrigger value="subjects">Subjects</TabsTrigger><TabsTrigger value="assign" data-testid="tab-assignments">Teacher assignments</TabsTrigger><TabsTrigger value="years" data-testid="tab-years">Academic years</TabsTrigger></TabsList>
        <TabsContent value="subjects"><CrudPage hideHeader title="Subjects" endpoint="/subjects" testid="subjects" fields={fields} defaults={{ type: "Theory", class_ids: [] }}
          columns={[{ key: "name", label: "Subject", render: (r) => <b>{r.name}</b> }, { key: "code", label: "Code" }, { key: "type", label: "Type" }, { key: "class_ids", label: "Classes", render: (r) => r.class_ids.map((c) => cn[c]).filter(Boolean).join(", ") || "—" }]} /></TabsContent>
        <TabsContent value="assign"><Assignments /></TabsContent>
        <TabsContent value="years"><CrudPage hideHeader title="Academic Years" endpoint="/academic-years" testid="years"
          fields={[{ name: "name", label: "Name (YYYY-YY)", required: true, placeholder: "2027-28" }, { name: "start_date", label: "Start", type: "date", required: true }, { name: "end_date", label: "End", type: "date", required: true }, { name: "current", label: "Set as current year", type: "switch" }]}
          columns={[{ key: "name", label: "Year", render: (r) => <b>{r.name}</b> }, { key: "start_date", label: "Start", render: (r) => fdate(r.start_date) }, { key: "end_date", label: "End", render: (r) => fdate(r.end_date) }, { key: "current", label: "", render: (r) => r.current && <Badge value="active" label="Current" /> }]} /></TabsContent>
      </Tabs>
    </div>
  );
}

function MySubjects() {
  const { data, loading } = useFetch("/assignments");
  return <div className="page"><PageHeader title="My Subjects" subtitle="Classes and subjects assigned to you" /><Section>
    <DataTable loading={loading} rows={data} testid="my-subjects-table" empty={<Empty title="No subjects assigned" />} columns={[{ key: "class_name", label: "Class", render: (r) => `${r.class_name}-${r.section}` }, { key: "subject_name", label: "Subject" }]} /></Section></div>;
}

export function Timetable() {
  const { user, childId } = useAuth(); const { classes, subjects } = useOptions(); const teachers = useFetch(user.role === "admin" ? "/teachers" : null, { page_size: 500, sort: "name" });
  const [view, setView] = useState(user.role === "teacher" ? "teacher" : "class");
  const [cls, setCls] = useState(""); const [sec, setSec] = useState(""); const [tch, setTch] = useState("");
  const params = user.role === "parent" || user.role === "student" ? { student_id: childId || undefined } : view === "teacher" ? { teacher_id: tch || undefined } : { class_id: cls, section: sec };
  const ready = user.role !== "admin" || (view === "class" ? cls && sec : tch);
  const { data, loading, reload } = useFetch(ready ? "/timetable" : null, params, [childId]);
  const [slot, setSlot] = useState(null);
  const days = data?.working_days || ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const at = (d, p) => (data?.entries || []).find((e) => e.day === d && e.period_no === p);
  const editable = user.role === "admin" && view === "class";
  const asgn = useFetch(editable && cls ? "/assignments" : null, { class_id: cls });
  const save = async (f) => { await api.post("/timetable", { ...f, class_id: cls, section: sec, day: slot.day, period_no: slot.period_no }); toast.success("Period saved"); reload(); };
  const del = async () => { try { await api.delete(`/timetable/${slot.id}`); toast.success("Cleared"); setSlot(null); reload(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <div className="page" data-testid="timetable-page">
      <PageHeader title="Timetable" subtitle={editable ? "Click any period to assign a subject. Teacher and room conflicts are checked before saving." : "Weekly schedule"} actions={<Button variant="outline" onClick={() => window.print()} data-testid="print-timetable-btn"><Printer className="h-4 w-4 mr-2" />Print</Button>} />
      {user.role === "admin" && <Section><div className="flex flex-wrap gap-3">
        <div className="w-40"><SelectField value={view} onChange={setView} options={[{ value: "class", label: "Class-wise" }, { value: "teacher", label: "Teacher-wise" }]} testid="tt-view" /></div>
        {view === "class" ? <><div className="w-44"><SelectField value={cls} onChange={(v) => { setCls(v); setSec(""); }} placeholder="Class" options={classes.map((c) => ({ value: c.id, label: c.name }))} testid="tt-class" /></div>
          <div className="w-32"><SelectField value={sec} onChange={setSec} placeholder="Section" options={(classes.find((c) => c.id === cls)?.sections || []).map((s) => ({ value: s.name, label: s.name }))} testid="tt-section" /></div></>
          : <div className="w-56"><SelectField value={tch} onChange={setTch} placeholder="Teacher" options={(teachers.data?.items || []).map((t) => ({ value: t.id, label: t.name }))} testid="tt-teacher" /></div>}
      </div></Section>}
      {!ready ? <Empty title="Choose what to view" /> : loading && !data ? <Loading /> : (
        <div className="card-surface overflow-x-auto print-area">
          <table className="w-full text-sm border-collapse min-w-[760px]" data-testid="timetable-grid">
            <thead><tr><th className="p-3 text-left text-xs uppercase text-muted-foreground w-28">Period</th>{days.map((d) => <th key={d} className="p-3 text-xs uppercase text-muted-foreground">{d}</th>)}</tr></thead>
            <tbody>{(data?.periods || []).map((p) => (
              <tr key={p.no} className="border-t">
                <td className="p-3 text-xs"><b>{p.type === "class" ? `P${p.no}` : p.type.toUpperCase()}</b><span className="block text-muted-foreground">{p.start}–{p.end}</span></td>
                {days.map((d) => { const e = at(d, p.no);
                  if (p.type !== "class") return <td key={d} className="p-2 text-center text-[11px] text-muted-foreground bg-muted/40 capitalize">{p.type}</td>;
                  return <td key={d} className="p-1.5"><button disabled={!editable} onClick={() => setSlot({ day: d, period_no: p.no, ...(e || {}) })} data-testid={`slot-${d}-${p.no}`}
                    className={`w-full min-h-[58px] rounded-lg p-2 text-left text-xs transition-colors ${e ? "bg-sky-50 dark:bg-sky-500/10 border border-sky-200 dark:border-sky-500/20" : "border border-dashed"} ${editable ? "hover:border-amber-400" : ""}`}>
                    {e ? <><b className="block">{e.subject_name}</b><span className="text-muted-foreground">{view === "teacher" || user.role === "teacher" ? `${e.class_name}-${e.section}` : e.teacher_name}{e.room ? ` · ${e.room}` : ""}</span></> : editable && <span className="text-muted-foreground">+ Add</span>}</button></td>; })}
              </tr>))}</tbody>
          </table>
        </div>)}
      <FormDialog open={!!slot} onOpenChange={(o) => !o && setSlot(null)} title={`${slot?.day} · Period ${slot?.period_no}`} initial={slot} testid="slot-form" onSubmit={save}
        fields={[{ name: "subject_id", label: "Subject", type: "select", required: true, options: subjects.map((s) => ({ value: s.id, label: s.name })),
          onChange: (v) => { const a = (asgn.data || []).find((x) => x.section === sec && x.subject_id === v); return a ? { teacher_id: a.teacher_id } : {}; } },
          { name: "teacher_id", label: "Teacher", type: "select", required: true, options: (teachers.data?.items || []).map((t) => ({ value: t.id, label: t.name })) }, { name: "room", label: "Room" },
          ...(slot?.id ? [{ name: "_clear", label: "", type: "custom", render: () => <Button type="button" variant="outline" className="text-rose-600" onClick={del} data-testid="clear-slot-btn"><Trash2 className="h-4 w-4 mr-1" />Clear this period</Button> }] : [])]} />
    </div>
  );
}

export function SaveBar({ onSave, busy, label = "Save", extra }) {
  return <div className="sticky bottom-4 flex justify-end gap-2 no-print">{extra}<Button onClick={onSave} disabled={busy} className="shadow-lg" data-testid="save-bar-btn"><Save className="h-4 w-4 mr-2" />{label}</Button></div>;
}
