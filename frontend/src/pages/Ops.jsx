import { useState } from "react";
import { BookUp, Undo2, Printer, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import CrudPage from "@/components/app/CrudPage";
import { FormDialog, SelectField } from "@/components/app/FormDialog";
import { DataTable, useTableState } from "@/components/app/DataTable";
import { useFetch, PageHeader, Section, Badge, Loading, Confirm } from "@/components/app/common";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fdate, inr, fdatetime } from "@/lib/fmt";

function Issues() {
  const { user } = useAuth(); const t = useTableState(); const { data, loading, reload } = useFetch("/library/issues", { page: t.page, status: t.filters.status });
  const [o, setO] = useState(false); const books = useFetch(user.role === "admin" ? "/books" : null, { page_size: 500, sort: "title" });
  const studs = useFetch(user.role === "admin" ? "/students" : null, { page_size: 500, sort: "name" }); const tch = useFetch(user.role === "admin" ? "/teachers" : null, { page_size: 500 });
  const ret = async (i) => { try { const { data: d } = await api.post(`/library/issues/${i.id}/return`); toast.success(d.fine ? `Returned · fine ${inr(d.fine)} (${d.days_late} days late)` : "Returned on time"); reload(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <Section action={user.role === "admin" && <Button onClick={() => setO(true)} data-testid="issue-book-btn"><BookUp className="h-4 w-4 mr-1" />Issue book</Button>}>
      <div className="w-44 mb-4"><SelectField value={t.filters.status || ""} onChange={(v) => t.setFilter("status", v)} allowEmpty="All" options={[{ value: "issued", label: "Issued" }, { value: "overdue", label: "Overdue" }, { value: "returned", label: "Returned" }]} testid="issue-status-filter" /></div>
      <DataTable loading={loading} rows={data?.items} page={t.page} total={data?.total} onPage={t.setPage} testid="issues-table" columns={[{ key: "book_title", label: "Book", render: (r) => <span><b>{r.book_title}</b><span className="block text-xs text-muted-foreground">{r.accession_no}</span></span> },
        { key: "borrower_name", label: "Borrower", render: (r) => `${r.borrower_name} (${r.borrower_type})` }, { key: "issue_date", label: "Issued", render: (r) => fdate(r.issue_date) }, { key: "due_date", label: "Due", render: (r) => fdate(r.due_date) },
        { key: "status", label: "Status", render: (r) => <Badge value={r.overdue ? "overdue" : r.status} /> }, { key: "fine", label: "Fine", render: (r) => (r.fine ? inr(r.fine) : "—") },
        { key: "a", label: "", render: (r) => user.role === "admin" && r.status === "issued" && <Button size="sm" variant="outline" onClick={() => ret(r)} data-testid={`return-${r.id}`}><Undo2 className="h-4 w-4 mr-1" />Return</Button> }]} />
      <FormDialog open={o} onOpenChange={setO} title="Issue a book" testid="issue-form" initial={{ borrower_type: "student" }}
        fields={[{ name: "book_id", label: "Book", type: "select", required: true, options: (books.data?.items || []).map((b) => ({ value: b.id, label: `${b.title} (${b.available_copies} available)` })) },
          { name: "borrower_type", label: "Borrower type", type: "select", options: [{ value: "student", label: "Student" }, { value: "teacher", label: "Staff" }], onChange: () => ({ borrower_id: "" }) },
          { name: "borrower_id", label: "Borrower", type: "select", required: true, options: (f) => ((f.borrower_type === "teacher" ? tch : studs).data?.items || []).map((p) => ({ value: p.id, label: p.name })) },
          { name: "due_date", label: "Return by (default per policy)", type: "date" }]}
        onSubmit={async (f) => { await api.post("/library/issue", { ...f, due_date: f.due_date || null }); toast.success("Book issued"); reload(); books.reload(); }} />
    </Section>
  );
}

export function Library() {
  const { user } = useAuth();
  const books = <CrudPage hideHeader title="Books" endpoint="/books" testid="books" searchPlaceholder="Title, author, ISBN…" defaults={{ total_copies: 1 }}
    fields={[{ name: "title", label: "Title", required: true, full: true }, { name: "author", label: "Author", required: true }, { name: "isbn", label: "ISBN" }, { name: "category", label: "Category" }, { name: "publisher", label: "Publisher" },
      { name: "total_copies", label: "Total copies", type: "number", required: true, min: 1 }, { name: "shelf", label: "Shelf" }]}
    columns={[{ key: "title", label: "Book", render: (r) => <span><b>{r.title}</b><span className="block text-xs text-muted-foreground">{r.author}</span></span> }, { key: "accession_no", label: "Accession" }, { key: "isbn", label: "ISBN" },
      { key: "category", label: "Category" }, { key: "available_copies", label: "Available", render: (r) => <Badge value={r.available_copies ? "active" : "absent"} label={`${r.available_copies}/${r.total_copies}`} /> }]} />;
  return (<div className="page" data-testid="library-page"><PageHeader title="Library" subtitle="Catalogue, issues, returns and fines" />
    <Tabs defaultValue="books"><TabsList><TabsTrigger value="books">Catalogue</TabsTrigger><TabsTrigger value="issues" data-testid="tab-issues">{user.role === "admin" ? "Issues & returns" : "My borrowings"}</TabsTrigger></TabsList>
      <TabsContent value="books">{books}</TabsContent><TabsContent value="issues"><Issues /></TabsContent></Tabs></div>);
}

function StopsEditor({ value, set }) {
  const arr = value || [];
  return (<div className="space-y-2">{arr.map((s, i) => <div key={i} className="flex gap-2"><input className="flex-1 h-9 rounded-md border px-2 text-sm bg-background" value={s.name} placeholder="Stop name" onChange={(e) => set(arr.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} data-testid={`stop-name-${i}`} />
    <input type="time" className="w-28 h-9 rounded-md border px-2 text-sm bg-background" value={s.time || ""} onChange={(e) => set(arr.map((x, j) => (j === i ? { ...x, time: e.target.value } : x)))} /><button type="button" onClick={() => set(arr.filter((_, j) => j !== i))} aria-label="Remove stop"><Trash2 className="h-4 w-4 text-rose-500" /></button></div>)}
    <Button type="button" size="sm" variant="outline" onClick={() => set([...arr, { name: "", time: "" }])} data-testid="add-stop-btn"><Plus className="h-4 w-4 mr-1" />Add stop</Button></div>);
}

function Allocation() {
  const { user } = useAuth(); const { data, loading, reload } = useFetch("/transport/overview"); const [o, setO] = useState(false); const studs = useFetch(user.role === "admin" ? "/students" : null, { page_size: 500, sort: "name" });
  if (loading && !data) return <Loading />;
  return (<div className="space-y-4 print-area">
    {user.role === "admin" && <div className="flex gap-2 no-print"><Button onClick={() => setO(true)} data-testid="assign-transport-btn">Assign student</Button><Button variant="outline" onClick={() => window.print()} data-testid="print-routes-btn"><Printer className="h-4 w-4 mr-1" />Print route lists</Button></div>}
    {data.routes.map((r) => <Section key={r.id} title={<span>{r.name} <span className="text-xs text-muted-foreground font-normal">{r.vehicle ? `${r.vehicle.reg_no} · ${r.students.length}/${r.vehicle.capacity} seats · Driver ${r.vehicle.driver_name} ${r.vehicle.driver_phone || ""}` : "No vehicle"}</span></span>} testid={`route-${r.id}`}>
      <p className="text-xs text-muted-foreground mb-2">Stops: {r.stops.map((s) => `${s.name}${s.time ? ` (${s.time})` : ""}`).join(" → ")}</p>
      <DataTable rows={r.students} testid={`route-students-${r.id}`} columns={[{ key: "name", label: "Student", render: (s) => `${s.name} (${s.admission_no})` }, { key: "class_name", label: "Class", render: (s) => `${s.class_name}-${s.section}` }, { key: "stop", label: "Stop", render: (s) => s.transport?.stop }, { key: "guardian_phone", label: "Guardian" },
        { key: "x", label: "", render: (s) => user.role === "admin" && <Confirm title="Remove from route?" onConfirm={() => api.post("/transport/assign", { student_id: s.id, route_id: null }).then(() => { toast.success("Removed"); reload(); })} trigger={<Button size="sm" variant="ghost" className="no-print" data-testid={`unassign-${s.id}`}>Remove</Button>} /> }]} /></Section>)}
    {user.role === "admin" && <Section title="Assignment history" className="no-print">{data.history.map((h) => <p key={h.id} className="text-xs py-1">{fdatetime(h.at)} · {h.student_name} → {data.routes.find((r) => r.id === h.route_id)?.name || "removed"} {h.stop && `(${h.stop})`} · by {h.by}</p>)}</Section>}
    <FormDialog open={o} onOpenChange={setO} title="Assign transport" testid="transport-form" fields={[{ name: "student_id", label: "Student", type: "select", required: true, options: (studs.data?.items || []).map((s) => ({ value: s.id, label: `${s.name} (${s.class_name}-${s.section})` })) },
      { name: "route_id", label: "Route", type: "select", required: true, options: data.routes.map((r) => ({ value: r.id, label: r.name })), onChange: () => ({ stop: "" }) },
      { name: "stop", label: "Stop", type: "select", required: true, options: (f) => (data.routes.find((r) => r.id === f.route_id)?.stops || []).map((s) => ({ value: s.name, label: s.name })) }]}
      onSubmit={async (f) => { await api.post("/transport/assign", f); toast.success("Assigned"); reload(); }} />
  </div>);
}

export function Transport() {
  const { user } = useAuth(); const vs = useFetch("/vehicles", { page_size: 100 });
  return (<div className="page" data-testid="transport-page"><PageHeader title="Transport" subtitle="Vehicles, routes, stops and student allocation. Live GPS tracking is not configured." />
    <Tabs defaultValue="alloc"><TabsList><TabsTrigger value="alloc">Route allocation</TabsTrigger>{user.role === "admin" && <><TabsTrigger value="routes" data-testid="tab-routes">Routes</TabsTrigger><TabsTrigger value="vehicles" data-testid="tab-vehicles">Vehicles</TabsTrigger></>}</TabsList>
      <TabsContent value="alloc"><Allocation /></TabsContent>
      {user.role === "admin" && <><TabsContent value="routes"><CrudPage hideHeader title="Routes" endpoint="/routes" testid="routes" defaults={{ stops: [], fee: 0 }}
        fields={[{ name: "name", label: "Route name", required: true }, { name: "vehicle_id", label: "Vehicle", type: "select", allowEmpty: true, options: (vs.data?.items || []).map((v) => ({ value: v.id, label: `${v.reg_no} (${v.capacity} seats)` })) },
          { name: "fee", label: "Annual fee (₹)", type: "number" }, { name: "stops", label: "Stops", type: "custom", full: true, render: (p) => <StopsEditor {...p} /> }]}
        toPayload={(f) => ({ ...f, vehicle_id: f.vehicle_id || null })} columns={[{ key: "name", label: "Route", render: (r) => <b>{r.name}</b> }, { key: "stops", label: "Stops", render: (r) => r.stops.map((s) => s.name).join(" → ") }, { key: "fee", label: "Fee", render: (r) => inr(r.fee) }]} /></TabsContent>
      <TabsContent value="vehicles"><CrudPage hideHeader title="Vehicles" endpoint="/vehicles" testid="vehicles"
        fields={[{ name: "reg_no", label: "Registration no.", required: true }, { name: "model", label: "Model" }, { name: "capacity", label: "Capacity", type: "number", required: true }, { name: "driver_name", label: "Driver" }, { name: "driver_phone", label: "Driver phone" }, { name: "attendant_name", label: "Attendant" }, { name: "attendant_phone", label: "Attendant phone" }]}
        columns={[{ key: "reg_no", label: "Vehicle", render: (r) => <span><b>{r.reg_no}</b><span className="block text-xs text-muted-foreground">{r.model}</span></span> }, { key: "capacity", label: "Seats" }, { key: "driver_name", label: "Driver", render: (r) => `${r.driver_name} · ${r.driver_phone}` }, { key: "attendant_name", label: "Attendant" }]} /></TabsContent></>}
    </Tabs></div>);
}
