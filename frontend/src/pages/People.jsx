import { useState } from "react";
import { KeyRound, Power, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import CrudPage from "@/components/app/CrudPage";
import { FormDialog, SelectField } from "@/components/app/FormDialog";
import { DataTable, SearchInput, useTableState } from "@/components/app/DataTable";
import { useFetch, useOptions, Badge, PageHeader, Section, Confirm } from "@/components/app/common";
import { api, errMsg } from "@/lib/api";
import { fdate, fdatetime, inr } from "@/lib/fmt";

const loginFields = [{ name: "email", label: "Login email", type: "email", required: true }, { name: "password", label: "Temporary password", type: "password", required: true, help: "Min 8 characters with letters and numbers" }];

function LoginBtn({ kind, r }) {
  const [o, setO] = useState(false);
  return <><Button variant="ghost" size="icon" title="Create portal login" onClick={() => setO(true)} data-testid={`create-login-${r.id}`}><KeyRound className="h-4 w-4" /></Button>
    <FormDialog open={o} onOpenChange={setO} title={`Create login for ${r.name}`} fields={loginFields} initial={{ email: r.email }} onSubmit={async (f) => { await api.post(`/${kind}/${r.id}/create-login`, f); toast.success("Login created"); }} testid="login-dialog" /></>;
}

export function Teachers() {
  const fields = [
    { name: "name", label: "Full name", required: true }, { name: "photo_file_id", label: "Profile photo", type: "file", context: "photo", accept: "image/*" },
    { name: "email", label: "Email", type: "email", required: true }, { name: "phone", label: "Phone", required: true },
    { name: "designation", label: "Designation", required: true }, { name: "department", label: "Department" }, { name: "specialization", label: "Subject specialization" },
    { name: "joining_date", label: "Joining date", type: "date", required: true }, { name: "qualification", label: "Qualification" }, { name: "experience_years", label: "Experience (years)", type: "number", min: 0 },
    { name: "salary", label: "Monthly salary (₹, admin only)", type: "number", min: 0 },
    { name: "status", label: "Employment status", type: "select", options: [["active", "Active"], ["on_leave", "On leave"], ["resigned", "Resigned"]].map(([v, l]) => ({ value: v, label: l })) },
    { name: "address", label: "Address", type: "textarea", full: true },
  ];
  const cols = [
    { key: "name", label: "Name", render: (r) => <span><b>{r.name}</b><span className="block text-xs text-muted-foreground">{r.employee_id} · {r.email}</span></span> },
    { key: "designation", label: "Designation" }, { key: "department", label: "Department" }, { key: "phone", label: "Phone" },
    { key: "joining_date", label: "Joined", render: (r) => fdate(r.joining_date) }, { key: "salary", label: "Salary", render: (r) => (r.salary != null ? inr(r.salary) : "—") },
    { key: "status", label: "Status", render: (r) => <Badge value={r.archived ? "archived" : r.status} /> },
  ];
  return <CrudPage title="Teachers & Staff" subtitle="Employee IDs are generated automatically" endpoint="/teachers" columns={cols} fields={fields} testid="teachers" exportName="staff"
    defaults={{ status: "active", designation: "Teacher", experience_years: 0 }} toPayload={(f) => ({ ...f, salary: f.salary === "" ? null : f.salary })}
    filters={[{ name: "status", label: "Status", options: [{ value: "active", label: "Active" }, { value: "on_leave", label: "On leave" }, { value: "resigned", label: "Resigned" }] }]}
    rowActions={(r) => <LoginBtn kind="teachers" r={r} />} />;
}

export function Parents() {
  const studs = useFetch("/students", { page_size: 500, sort: "name" });
  const fields = [{ name: "name", label: "Full name", required: true }, { name: "relation", label: "Relation", type: "select", options: ["Father", "Mother", "Guardian", "Parent"].map((v) => ({ value: v, label: v })) },
    { name: "email", label: "Email", type: "email", required: true }, { name: "phone", label: "Phone", required: true }, { name: "occupation", label: "Occupation" },
    { name: "student_ids", label: "Linked children", type: "multicheck", full: true, options: (studs.data?.items || []).map((s) => ({ value: s.id, label: `${s.name} (${s.class_name}-${s.section})` })) },
    { name: "address", label: "Address", type: "textarea", full: true }];
  const sname = Object.fromEntries((studs.data?.items || []).map((s) => [s.id, s.name]));
  const cols = [{ key: "name", label: "Name", render: (r) => <span><b>{r.name}</b><span className="block text-xs text-muted-foreground">{r.relation}</span></span> }, { key: "email", label: "Email" }, { key: "phone", label: "Phone" },
    { key: "student_ids", label: "Children", render: (r) => (r.student_ids || []).map((i) => sname[i] || "—").join(", ") || "—" }];
  return <CrudPage title="Parents" subtitle="Link parents to their children for portal access" endpoint="/parents" columns={cols} fields={fields} testid="parents" exportName="parents" defaults={{ relation: "Parent", student_ids: [] }} rowActions={(r) => <LoginBtn kind="parents" r={r} />} />;
}

export function Users() {
  const t = useTableState();
  const { data, loading, error, reload } = useFetch("/users", { q: t.q, page: t.page, role: t.filters.role, pending: t.filters.pending === "1" || undefined });
  const pend = useFetch("/users", { pending: true, page_size: 1 }, [data]);
  const [edit, setEdit] = useState(null); const [reset, setReset] = useState(null);
  const teachers = useFetch("/teachers", { page_size: 500 }); const studs = useFetch("/students", { page_size: 500 }); const parents = useFetch("/parents", { page_size: 500 });
  const prof = (role) => ({ teacher: teachers, student: studs, parent: parents }[role]?.data?.items || []).map((p) => ({ value: p.id, label: p.name }));
  const fields = [{ name: "name", label: "Display name", required: true }, { name: "email", label: "Email", type: "email", required: true },
    { name: "role", label: "Role", type: "select", required: true, options: ["admin", "teacher", "student", "parent"].map((r) => ({ value: r, label: r[0].toUpperCase() + r.slice(1) })), onChange: () => ({ profile_id: "" }) },
    { name: "profile_id", label: "Linked profile", type: "select", options: (f) => prof(f.role), hidden: (f) => !f.role || f.role === "admin", required: true },
    { name: "password", label: "Password", type: "password", hidden: (f) => !!f.id, required: true, help: "Min 8 characters with letters and numbers" }, { name: "active", label: "Active", type: "switch" }];
  const toggle = async (u) => { try { await api.post(`/users/${u.id}/toggle-active`); toast.success("Updated"); reload(); } catch (e) { toast.error(errMsg(e)); } };
  const cols = [{ key: "name", label: "User", render: (r) => <span><b>{r.name}</b><span className="block text-xs text-muted-foreground">{r.email}</span></span> }, { key: "role", label: "Role", render: (r) => <Badge value={r.role} /> },
    { key: "active", label: "Status", render: (r) => r.pending ? <span><Badge value="pending" label="Awaiting approval" />{r.signup_note && <span className="block text-[11px] text-muted-foreground mt-1 max-w-[220px] truncate" title={r.signup_note}>{r.signup_note}</span>}{r.phone && <span className="block text-[11px] text-muted-foreground">{r.phone}</span>}</span> : <Badge value={r.active ? "active" : "inactive"} /> }, { key: "last_login", label: "Last login", render: (r) => fdatetime(r.last_login) },
    { key: "a", label: "", className: "text-right", render: (r) => r.pending ? <div className="flex justify-end gap-1">
      <Button size="sm" onClick={() => setEdit({ ...r, active: true })} data-testid={`user-approve-${r.id}`}>Approve</Button>
      <Confirm title="Reject this account request?" description="The request will be deleted." onConfirm={() => api.delete(`/users/${r.id}/request`).then(() => { toast.success("Request rejected"); reload(); }).catch((e) => toast.error(errMsg(e)))}
        trigger={<Button size="sm" variant="outline" className="text-rose-600" data-testid={`user-reject-${r.id}`}>Reject</Button>} /></div> : <div className="flex justify-end gap-1">
      <Button variant="ghost" size="sm" onClick={() => setEdit(r)} data-testid={`user-edit-${r.id}`}>Edit</Button>
      <Button variant="ghost" size="icon" title="Reset password" onClick={() => setReset(r)} data-testid={`user-reset-${r.id}`}><KeyRound className="h-4 w-4" /></Button>
      <Confirm title={r.active ? "Deactivate this account?" : "Activate this account?"} description="Active sessions will be signed out." onConfirm={() => toggle(r)} destructive={r.active}
        trigger={<Button variant="ghost" size="icon" title={r.active ? "Deactivate" : "Activate"} data-testid={`user-toggle-${r.id}`}><Power className={`h-4 w-4 ${r.active ? "text-rose-500" : "text-emerald-600"}`} /></Button>} /></div> }];
  return (
    <div className="page" data-testid="users-page">
      <PageHeader title="User Management" subtitle="Portal accounts, roles and access" actions={<Button onClick={() => setEdit({ active: true })} data-testid="add-user-btn"><Plus className="h-4 w-4 mr-2" />Add user</Button>} />
      <Section><div className="flex flex-col sm:flex-row gap-3 mb-4"><SearchInput value={t.q} onChange={t.setSearch} testid="users-search" />
        <div className="w-full sm:w-48"><SelectField value={t.filters.role || ""} onChange={(v) => t.setFilter("role", v)} allowEmpty="All roles" options={["admin", "teacher", "student", "parent"].map((r) => ({ value: r, label: r }))} testid="users-role-filter" /></div>
        <Button variant={t.filters.pending === "1" ? "default" : "outline"} onClick={() => t.setFilter("pending", t.filters.pending === "1" ? "" : "1")} data-testid="users-pending-filter">Pending requests{pend.data?.total ? ` (${pend.data.total})` : ""}</Button></div>
        <DataTable columns={cols} rows={data?.items} loading={loading} error={error} onRetry={reload} page={t.page} total={data?.total} onPage={t.setPage} testid="users-table" /></Section>
      <FormDialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)} title={edit?.pending ? "Approve account request" : edit?.id ? "Edit user" : "Add user"} description={edit?.pending ? "Link this account to the matching teacher, student or parent profile, then save to approve." : undefined} fields={fields} initial={edit} testid="user-form"
        onSubmit={async (f) => { const b = { ...f, profile_id: f.role === "admin" ? null : f.profile_id }; if (f.id) await api.put(`/users/${f.id}`, b); else await api.post("/users", b); toast.success(f.pending ? "Account approved; the user was emailed" : "Saved"); reload(); }} />
      <FormDialog open={!!reset} onOpenChange={(o) => !o && setReset(null)} title={`Reset password for ${reset?.name}`} fields={[{ name: "password", label: "New password", type: "password", required: true }]} testid="reset-form"
        onSubmit={async (f) => { await api.post(`/users/${reset.id}/reset-password`, f); toast.success("Password reset; user's sessions were signed out"); }} />
    </div>
  );
}

export function Classes() {
  const teachers = useFetch("/teachers", { page_size: 500, sort: "name" });
  const ov = useFetch("/classes-overview");
  const counts = Object.fromEntries((ov.data || []).map((c) => [c.id, c.sections]));
  const SecEditor = ({ value, set }) => {
    const arr = value || [];
    const upd = (i, k, v) => set(arr.map((s, j) => (j === i ? { ...s, [k]: v } : s)));
    return (<div className="space-y-2">{arr.map((s, i) => (
      <div key={i} className="grid grid-cols-12 gap-2 items-center">
        <input className="col-span-2 h-9 rounded-md border px-2 text-sm bg-background" value={s.name} onChange={(e) => upd(i, "name", e.target.value)} placeholder="A" data-testid={`section-name-${i}`} />
        <input className="col-span-2 h-9 rounded-md border px-2 text-sm bg-background" type="number" value={s.capacity} onChange={(e) => upd(i, "capacity", Number(e.target.value))} title="Capacity" />
        <input className="col-span-2 h-9 rounded-md border px-2 text-sm bg-background" value={s.room || ""} onChange={(e) => upd(i, "room", e.target.value)} placeholder="Room" />
        <div className="col-span-5"><SelectField value={s.class_teacher_id || ""} onChange={(v) => upd(i, "class_teacher_id", v || null)} allowEmpty="No class teacher" options={(teachers.data?.items || []).map((t) => ({ value: t.id, label: t.name }))} testid={`section-teacher-${i}`} /></div>
        <button type="button" className="col-span-1" onClick={() => set(arr.filter((_, j) => j !== i))} aria-label="Remove section"><Trash2 className="h-4 w-4 text-rose-500" /></button>
      </div>))}
      <Button type="button" variant="outline" size="sm" onClick={() => set([...arr, { name: String.fromCharCode(65 + arr.length), capacity: 40, room: "", class_teacher_id: null }])} data-testid="add-section-btn"><Plus className="h-4 w-4 mr-1" />Add section</Button></div>);
  };
  const fields = [{ name: "name", label: "Class name", required: true, placeholder: "Grade 6" }, { name: "grade_level", label: "Grade level", type: "number", required: true, min: 0, max: 14 },
    { name: "sections", label: "Sections (name · capacity · room · class teacher)", type: "custom", full: true, render: (p) => <SecEditor {...p} />, validate: (v) => (!v?.length ? "Add at least one section" : null) }];
  const tname = Object.fromEntries((teachers.data?.items || []).map((t) => [t.id, t.name]));
  const cols = [{ key: "name", label: "Class", render: (r) => <b>{r.name}</b> }, { key: "grade_level", label: "Level" },
    { key: "sections", label: "Sections", render: (r) => <div className="flex flex-wrap gap-2">{r.sections.map((s) => { const c = (counts[r.id] || []).find((x) => x.name === s.name); return <span key={s.name} className="rounded-md bg-secondary px-2 py-1 text-xs">{s.name}: {c?.student_count ?? 0}/{s.capacity} · {tname[s.class_teacher_id] || "no class teacher"}</span>; })}</div> }];
  return <CrudPage title="Classes & Sections" subtitle="Grade levels, sections, capacity and class teachers" endpoint="/classes" columns={cols} fields={fields} testid="classes" defaults={{ sections: [{ name: "A", capacity: 40, room: "" }] }} toPayload={(f) => ({ name: f.name, grade_level: f.grade_level, sections: f.sections })} />;
}
