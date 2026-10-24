import { useState } from "react";
import { Search, ChevronLeft, ChevronRight } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Loading, Empty, ErrorBox } from "./common";

export function SearchInput({ value, onChange, placeholder = "Search…", testid = "table-search-input" }) {
  return (
    <div className="relative w-full sm:w-72">
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
      <Input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="pl-9" data-testid={testid} />
    </div>
  );
}

export function DataTable({ columns, rows, loading, error, onRetry, empty, page, total, pageSize = 20, onPage, rowKey = "id", onRowClick, testid = "data-table" }) {
  const pages = Math.max(1, Math.ceil((total || 0) / pageSize));
  if (loading && !rows?.length) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={onRetry} />;
  if (!rows?.length) return empty || <Empty />;
  return (
    <div data-testid={testid}>
      <div className="overflow-x-auto rounded-lg border">
        <Table>
          <TableHeader className="bg-muted/60 sticky top-0">
            <TableRow>{columns.map((c) => <TableHead key={c.key} className={`whitespace-nowrap text-xs uppercase tracking-wider ${c.className || ""}`}>{c.label}</TableHead>)}</TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r, i) => (
              <TableRow key={r[rowKey] || i} onClick={onRowClick ? () => onRowClick(r) : undefined} className={`${onRowClick ? "cursor-pointer" : ""} even:bg-muted/20 transition-colors`} data-testid={`${testid}-row-${i}`}>
                {columns.map((c) => <TableCell key={c.key} className={`py-3 ${c.className || ""}`}>{c.render ? c.render(r) : (r[c.key] ?? "—")}</TableCell>)}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {onPage && total > pageSize && (
        <div className="flex items-center justify-between mt-3 text-sm text-muted-foreground no-print">
          <span data-testid={`${testid}-total`}>{total} records · page {page} of {pages}</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)} data-testid={`${testid}-prev`}><ChevronLeft className="h-4 w-4" /></Button>
            <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)} data-testid={`${testid}-next`}><ChevronRight className="h-4 w-4" /></Button>
          </div>
        </div>
      )}
    </div>
  );
}

export function useTableState(initial = {}) {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState(initial);
  const setFilter = (k, v) => { setFilters((f) => ({ ...f, [k]: v })); setPage(1); };
  const setSearch = (v) => { setQ(v); setPage(1); };
  return { q, setSearch, page, setPage, filters, setFilter };
}
