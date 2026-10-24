import { useState } from "react";
import { Plus, Pencil, Archive, Download, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api, errMsg, downloadFile } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader, Section, useFetch, Confirm, Badge } from "./common";
import { DataTable, SearchInput, useTableState } from "./DataTable";
import { FormDialog, SelectField } from "./FormDialog";

// Config-driven list + create/edit/archive page for simple resources.
export default function CrudPage({ title, subtitle, endpoint, columns, fields, defaults = {}, filters = [], toPayload = (f) => f, canWrite = ["admin"],
  extraActions, rowActions, testid, wide = true, searchPlaceholder, exportName, hideHeader, onCreated }) {
  const { user } = useAuth();
  const t = useTableState();
  const [showArchived, setShowArchived] = useState(false);
  const { data, loading, error, reload } = useFetch(endpoint, { q: t.q, page: t.page, page_size: 20, include_archived: showArchived, ...t.filters });
  const [edit, setEdit] = useState(null);
  const writable = canWrite.includes(user?.role);

  const save = async (form) => {
    const body = toPayload(form);
    if (edit?.id) { await api.put(`${endpoint}/${edit.id}`, body); toast.success("Changes saved"); }
    else { const r = await api.post(endpoint, body); toast.success("Created successfully"); onCreated?.(r.data, form); }
    reload();
  };
  const archive = async (r) => {
    try { await api.delete(`${endpoint}/${r.id}`); toast.success("Archived"); reload(); } catch (e) { toast.error(errMsg(e)); }
  };
  const restore = async (r) => { try { await api.post(`${endpoint}/${r.id}/restore`); toast.success("Restored"); reload(); } catch (e) { toast.error(errMsg(e)); } };

  const cols = [...columns];
  if (writable || rowActions) cols.push({ key: "_actions", label: "", className: "text-right", render: (r) => (
    <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
      {rowActions?.(r, reload)}
      {writable && !r.archived && <Button variant="ghost" size="icon" onClick={() => setEdit(r)} aria-label="Edit" data-testid={`${testid}-edit-${r.id}`}><Pencil className="h-4 w-4" /></Button>}
      {writable && !r.archived && <Confirm title="Archive this record?" description="It will be hidden from lists but kept for history. You can restore it later."
        onConfirm={() => archive(r)} confirmLabel="Archive" trigger={<Button variant="ghost" size="icon" aria-label="Archive" data-testid={`${testid}-archive-${r.id}`}><Archive className="h-4 w-4" /></Button>} />}
      {writable && r.archived && <Button variant="ghost" size="sm" onClick={() => restore(r)} data-testid={`${testid}-restore-${r.id}`}><RotateCcw className="h-4 w-4 mr-1" />Restore</Button>}
    </div>) });

  return (
    <div className={hideHeader ? "space-y-4" : "page"} data-testid={testid}>
      {!hideHeader && <PageHeader title={title} subtitle={subtitle} actions={<>
        {extraActions}
        {exportName && <Button variant="outline" onClick={() => downloadFile(endpoint, { format: "csv", q: t.q, ...t.filters }, `${exportName}.csv`).catch((e) => toast.error(errMsg(e)))} data-testid={`${testid}-export-btn`}><Download className="h-4 w-4 mr-2" />Export CSV</Button>}
        {writable && <Button onClick={() => setEdit({})} className="bg-primary" data-testid={`${testid}-add-btn`}><Plus className="h-4 w-4 mr-2" />Add New</Button>}
      </>} />}
      {hideHeader && writable && <div className="flex justify-end"><Button onClick={() => setEdit({})} data-testid={`${testid}-add-btn`}><Plus className="h-4 w-4 mr-2" />Add New</Button></div>}
      <Section>
        <div className="flex flex-col sm:flex-row gap-3 mb-4 sm:items-center">
          <SearchInput value={t.q} onChange={t.setSearch} placeholder={searchPlaceholder} testid={`${testid}-search`} />
          {filters.map((f) => (
            <div key={f.name} className="w-full sm:w-48">
              <SelectField value={t.filters[f.name] || ""} onChange={(v) => t.setFilter(f.name, v)} options={f.options} placeholder={f.label} allowEmpty={`All ${f.label.toLowerCase()}`} testid={`${testid}-filter-${f.name}`} />
            </div>
          ))}
          {writable && <label className="flex items-center gap-2 text-xs text-muted-foreground sm:ml-auto"><input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} data-testid={`${testid}-show-archived`} />Show archived</label>}
        </div>
        <DataTable columns={cols.map((c) => c.key === "archived" ? { ...c, render: (r) => r.archived ? <Badge value="archived" /> : null } : c)} rows={data?.items} loading={loading} error={error} onRetry={reload}
          page={t.page} total={data?.total} onPage={t.setPage} testid={`${testid}-table`} />
      </Section>
      <FormDialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)} title={edit?.id ? `Edit ${title.replace(/s$/, "")}` : `Add ${title.replace(/s$/, "")}`}
        fields={fields} initial={edit?.id ? edit : defaults} onSubmit={save} wide={wide} testid={`${testid}-form`} />
    </div>
  );
}
