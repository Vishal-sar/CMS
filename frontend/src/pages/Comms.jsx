import { useState } from "react";
import { ChevronLeft, ChevronRight, Plus, Pin } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import CrudPage from "@/components/app/CrudPage";
import { FormDialog, SelectField } from "@/components/app/FormDialog";
import { DataTable, useTableState } from "@/components/app/DataTable";
import { useFetch, useOptions, PageHeader, Section, Badge, Loading, Empty, Confirm } from "@/components/app/common";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fdate, fdatetime, todayISO } from "@/lib/fmt";

const TYPE_C = { holiday: "bg-rose-500", closure: "bg-rose-700", exam: "bg-sky-600", ptm: "bg-amber-500", event: "bg-emerald-600", academic: "bg-indigo-600", deadline: "bg-slate-500" };

export function CalendarPage() {
  const { user } = useAuth(); const { classes } = useOptions(); const [m, setM] = useState(() => todayISO().slice(0, 7));
  const { data, loading, reload } = useFetch("/calendar", { month: m }); const [edit, setEdit] = useState(null);
  const [y, mo] = m.split("-").map(Number); const first = new Date(y, mo - 1, 1); const days = new Date(y, mo, 0).getDate(); const pad = (first.getDay() + 6) % 7;
  const shift = (d) => { const n = new Date(y, mo - 1 + d, 1); setM(`${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, "0")}`); };
  const on = (d) => { const iso = `${m}-${String(d).padStart(2, "0")}`; return (data || []).filter((e) => e.start_date <= iso && e.end_date >= iso); };
  const fields = [{ name: "title", label: "Title", required: true, full: true }, { name: "type", label: "Type", type: "select", required: true, options: ["holiday", "closure", "exam", "ptm", "event", "academic"].map((v) => ({ value: v, label: v.toUpperCase() === "PTM" ? "Parent-teacher meeting" : v[0].toUpperCase() + v.slice(1) })) },
    { name: "class_id", label: "Class (optional)", type: "select", allowEmpty: "All classes", options: classes.map((c) => ({ value: c.id, label: c.name })) },
    { name: "start_date", label: "Start", type: "date", required: true }, { name: "end_date", label: "End", type: "date", required: true, validate: (v, f) => (v < f.start_date ? "End must be after start" : null) }, { name: "description", label: "Description", type: "textarea", full: true }];
  const save = async (f) => { const b = { title: f.title, type: f.type, class_id: f.class_id || null, start_date: f.start_date, end_date: f.end_date, description: f.description || "" }; if (f.id) await api.put(`/events/${f.id}`, b); else await api.post("/events", b); toast.success("Event saved"); reload(); };
  return (
    <div className="page" data-testid="calendar-page">
      <PageHeader title="Calendar & Events" subtitle="Holidays, exams, meetings, events and homework deadlines" actions={user.role === "admin" && <Button onClick={() => setEdit({ start_date: todayISO(), end_date: todayISO(), type: "event" })} data-testid="add-event-btn"><Plus className="h-4 w-4 mr-2" />Add event</Button>} />
      <Section title={first.toLocaleDateString("en-IN", { month: "long", year: "numeric" })} action={<div className="flex gap-1"><Button size="icon" variant="outline" onClick={() => shift(-1)} data-testid="cal-prev"><ChevronLeft className="h-4 w-4" /></Button><Button size="icon" variant="outline" onClick={() => shift(1)} data-testid="cal-next"><ChevronRight className="h-4 w-4" /></Button></div>}>
        {loading && !data ? <Loading /> : <div className="grid grid-cols-7 gap-1 text-xs" data-testid="calendar-grid">
          {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => <div key={d} className="text-center font-semibold text-muted-foreground py-1">{d}</div>)}
          {Array.from({ length: pad }).map((_, i) => <div key={`p${i}`} />)}
          {Array.from({ length: days }, (_, i) => i + 1).map((d) => { const iso = `${m}-${String(d).padStart(2, "0")}`; return (
            <div key={d} className={`min-h-[84px] rounded-lg border p-1.5 ${iso === todayISO() ? "ring-2 ring-amber-400" : ""}`}><p className="font-semibold mb-1">{d}</p>
              {on(d).slice(0, 3).map((e) => <button key={e.id} disabled={e.auto || user.role !== "admin"} onClick={() => setEdit(e)} className={`block w-full truncate rounded px-1 py-0.5 mb-0.5 text-left text-[10px] text-white ${TYPE_C[e.type] || "bg-slate-500"}`} title={e.title} data-testid={`event-${e.id}`}>{e.title}</button>)}
              {on(d).length > 3 && <p className="text-[10px] text-muted-foreground">+{on(d).length - 3} more</p>}</div>); })}
        </div>}
        <div className="flex flex-wrap gap-3 mt-4 text-xs">{Object.entries(TYPE_C).map(([k, c]) => <span key={k} className="flex items-center gap-1 capitalize"><span className={`h-2.5 w-2.5 rounded ${c}`} />{k === "ptm" ? "PTM" : k}</span>)}</div>
      </Section>
      <FormDialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)} wide title={edit?.id ? "Edit event" : "Add event"} fields={[...fields, ...(edit?.id ? [{ name: "_d", label: "", type: "custom", render: () => <Confirm title="Delete this event?" onConfirm={() => api.delete(`/events/${edit.id}`).then(() => { toast.success("Removed"); setEdit(null); reload(); })} trigger={<Button type="button" variant="outline" className="text-rose-600" data-testid="delete-event-btn">Remove event</Button>} /> }] : [])]} initial={edit} onSubmit={save} testid="event-form" />
    </div>
  );
}

export function Leave() {
  const { user, childId } = useAuth(); const t = useTableState(); const { data, loading, reload } = useFetch("/leaves", { page: t.page, status: t.filters.status, kind: t.filters.kind });
  const [o, setO] = useState(false); const [rv, setRv] = useState(null); const kids = useFetch(user.role === "parent" ? "/students" : null);
  const canReview = (r) => r.status === "pending" && (user.role === "admin" || (user.role === "teacher" && r.kind === "student"));
  const fields = [...(user.role === "parent" ? [{ name: "student_id", label: "Child", type: "select", required: true, options: (kids.data?.items || []).map((k) => ({ value: k.id, label: k.name })) }] : []),
    { name: "leave_type", label: "Leave type", type: "select", required: true, options: ["Sick", "Casual", "Earned", "Personal", "Medical", "Family", "Other"].map((v) => ({ value: v, label: v })) },
    { name: "from_date", label: "From", type: "date", required: true }, { name: "to_date", label: "To", type: "date", required: true, validate: (v, f) => (v < f.from_date ? "End date must be on or after start date" : null) },
    { name: "reason", label: "Reason", type: "textarea", required: true, full: true, validate: (v) => (v && v.length < 3 ? "Please give a reason" : null) }];
  return (
    <div className="page" data-testid="leave-page">
      <PageHeader title="Leave Management" subtitle={user.role === "admin" ? "Review staff leave and student absence requests" : user.role === "parent" ? "Notify the school of your child's absence" : "Apply for leave and track decisions"}
        actions={user.role !== "admin" && <Button onClick={() => setO(true)} data-testid="apply-leave-btn"><Plus className="h-4 w-4 mr-2" />{user.role === "parent" ? "Absence notice" : "Apply for leave"}</Button>} />
      <Section><div className="flex gap-3 mb-4"><div className="w-40"><SelectField value={t.filters.status || ""} onChange={(v) => t.setFilter("status", v)} allowEmpty="All statuses" options={["pending", "approved", "rejected"].map((s) => ({ value: s, label: s }))} testid="leave-status-filter" /></div>
        {user.role === "admin" && <div className="w-40"><SelectField value={t.filters.kind || ""} onChange={(v) => t.setFilter("kind", v)} allowEmpty="Staff & students" options={[{ value: "staff", label: "Staff" }, { value: "student", label: "Students" }]} testid="leave-kind-filter" /></div>}</div>
        <DataTable loading={loading} rows={data?.items} page={t.page} total={data?.total} onPage={t.setPage} testid="leaves-table" empty={<Empty title="No leave requests" />} columns={[
          { key: "requester_name", label: "Request", render: (r) => <span><b>{r.student_name || r.requester_name}</b><span className="block text-xs text-muted-foreground">{r.kind === "student" ? `Student · by ${r.requester_name}` : "Staff"} · {r.leave_type}</span></span> },
          { key: "from_date", label: "Dates", render: (r) => `${fdate(r.from_date)} – ${fdate(r.to_date)}` }, { key: "reason", label: "Reason", className: "max-w-xs truncate" },
          { key: "status", label: "Status", render: (r) => <span><Badge value={r.status} />{r.reviewer && <span className="block text-[10px] text-muted-foreground">by {r.reviewer}{r.review_note && `: ${r.review_note}`}</span>}</span> },
          { key: "a", label: "", render: (r) => canReview(r) && <Button size="sm" variant="outline" onClick={() => setRv(r)} data-testid={`review-leave-${r.id}`}>Review</Button> }]} /></Section>
      <FormDialog open={o} onOpenChange={setO} wide title={user.role === "parent" ? "Absence notification" : "Leave request"} fields={fields} initial={{ leave_type: "Sick", from_date: todayISO(), to_date: todayISO(), student_id: childId }} testid="leave-form"
        onSubmit={async (f) => { await api.post("/leaves", f); toast.success("Request submitted"); reload(); }} />
      <FormDialog open={!!rv} onOpenChange={(x) => !x && setRv(null)} title="Review request" description={rv && `${rv.student_name || rv.requester_name}: ${rv.reason}`} initial={{ status: "approved" }} testid="review-form"
        fields={[{ name: "status", label: "Decision", type: "select", required: true, options: [{ value: "approved", label: "Approve" }, { value: "rejected", label: "Reject" }] }, { name: "note", label: "Note", type: "textarea" }]}
        onSubmit={async (f) => { await api.put(`/leaves/${rv.id}/review`, f); toast.success(`Request ${f.status}`); reload(); }} />
    </div>
  );
}

export function Announcements() {
  const { user } = useAuth(); const { classes } = useOptions();
  if (user.role === "student" || user.role === "parent") return <AnnList />;
  const fields = [{ name: "title", label: "Title", required: true, full: true }, { name: "category", label: "Category", type: "select", options: ["General", "Academic", "Event", "Holiday", "Urgent"].map((v) => ({ value: v, label: v })) }, { name: "pinned", label: "Pin to top", type: "switch" },
    { name: "roles", label: "Audience roles (none = everyone)", type: "multicheck", full: true, options: ["teacher", "student", "parent"].map((r) => ({ value: r, label: r[0].toUpperCase() + r.slice(1) + "s" })) },
    { name: "class_ids", label: user.role === "teacher" ? "Your classes (required)" : "Classes (none = all)", type: "multicheck", full: true, options: classes.map((c) => ({ value: c.id, label: c.name })) },
    { name: "body", label: "Message", type: "textarea", required: true, full: true, rows: 5 }];
  return <CrudPage title="Announcements" subtitle="Published notices create in-app notifications for the selected audience" endpoint="/announcements" testid="announcements" canWrite={["admin", "teacher"]} fields={fields} defaults={{ category: "General", roles: [], class_ids: [], pinned: false }}
    columns={[{ key: "title", label: "Announcement", render: (r) => <span><b className="flex items-center gap-1">{r.pinned && <Pin className="h-3 w-3 text-amber-500" />}{r.title}</b><span className="block text-xs text-muted-foreground line-clamp-1">{r.body}</span></span> },
      { key: "roles", label: "Audience", render: (r) => `${r.roles.length ? r.roles.join(", ") : "Everyone"}${r.class_ids.length ? ` · ${r.class_ids.length} class(es)` : ""}` }, { key: "author", label: "By" }, { key: "created_at", label: "Posted", render: (r) => fdatetime(r.created_at) }]} />;
}

function AnnList() {
  const { data, loading } = useFetch("/announcements", { page_size: 50 });
  return <div className="page"><PageHeader title="Announcements" subtitle="Notices from your school" />{loading ? <Loading /> : !data?.items.length ? <Empty title="No announcements" /> :
    <div className="space-y-3">{[...data.items].sort((a, b) => b.pinned - a.pinned).map((a) => <Section key={a.id} testid={`ann-${a.id}`} title={<span className="flex items-center gap-2">{a.pinned && <Pin className="h-4 w-4 text-amber-500" />}{a.title}</span>} action={<Badge value="submitted" label={a.category} />}>
      <p className="text-sm whitespace-pre-wrap">{a.body}</p><p className="text-xs text-muted-foreground mt-2">{a.author} · {fdatetime(a.created_at)}</p></Section>)}</div>}</div>;
}
