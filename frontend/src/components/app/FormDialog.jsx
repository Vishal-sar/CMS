import { useEffect, useState } from "react";
import { Loader2, Upload, X } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { errMsg, uploadFile } from "@/lib/api";

export function SelectField({ value, onChange, options, placeholder = "Select…", testid, allowEmpty }) {
  return (
    <Select value={value === null || value === undefined || value === "" ? (allowEmpty ? "__none" : undefined) : String(value)} onValueChange={(v) => onChange(v === "__none" ? "" : v)}>
      <SelectTrigger data-testid={testid}><SelectValue placeholder={placeholder} /></SelectTrigger>
      <SelectContent>
        {allowEmpty && <SelectItem value="__none">{typeof allowEmpty === "string" ? allowEmpty : "— None —"}</SelectItem>}
        {options.map((o) => <SelectItem key={o.value} value={String(o.value)} data-testid={`${testid}-opt-${String(o.value).replace(/\s+/g, "-").toLowerCase()}`}>{o.label}</SelectItem>)}
      </SelectContent>
    </Select>
  );
}

export function FileField({ value, onChange, context, accept, testid, multiple }) {
  const [busy, setBusy] = useState(false);
  const files = multiple ? value || [] : value ? [{ id: value }] : [];
  const pick = async (e) => {
    const f = e.target.files?.[0]; if (!f) return;
    if (f.size > 5 * 1024 * 1024) { toast.error("File exceeds 5 MB"); return; }
    setBusy(true);
    try {
      const r = await uploadFile(f, context);
      onChange(multiple ? [...files, { id: r.id, name: r.original_filename }] : r.id);
      toast.success("File uploaded");
    } catch (er) { toast.error(errMsg(er)); } finally { setBusy(false); e.target.value = ""; }
  };
  return (
    <div className="space-y-2">
      <label className="flex items-center gap-2 rounded-lg border border-dashed px-3 py-2 text-sm cursor-pointer hover:bg-muted/50 transition-colors">
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
        <span>{busy ? "Uploading…" : "Choose file (max 5 MB)"}</span>
        <input type="file" className="hidden" accept={accept} onChange={pick} data-testid={testid} />
      </label>
      {files.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {files.map((f) => (
            <span key={f.id} className="inline-flex items-center gap-1 rounded-md bg-secondary px-2 py-1 text-xs">
              {f.name || "Uploaded file"}
              <button type="button" onClick={() => onChange(multiple ? files.filter((x) => x.id !== f.id) : null)} aria-label="Remove file"><X className="h-3 w-3" /></button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function FieldInput({ f, value, set, form }) {
  const tid = `field-${f.name}`;
  if (f.type === "select") return <SelectField value={value} onChange={set} options={typeof f.options === "function" ? f.options(form) : f.options} testid={tid} allowEmpty={f.allowEmpty} />;
  if (f.type === "textarea") return <Textarea value={value ?? ""} onChange={(e) => set(e.target.value)} rows={f.rows || 3} data-testid={tid} />;
  if (f.type === "switch") return <div className="pt-1"><Switch checked={!!value} onCheckedChange={set} data-testid={tid} /></div>;
  if (f.type === "file") return <FileField value={value} onChange={set} context={f.context} accept={f.accept} testid={tid} multiple={f.multiple} />;
  if (f.type === "multicheck") {
    const opts = typeof f.options === "function" ? f.options(form) : f.options; const arr = value || [];
    return (
      <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto" data-testid={tid}>
        {opts.map((o) => {
          const on = arr.includes(o.value);
          return <button type="button" key={o.value} onClick={() => set(on ? arr.filter((x) => x !== o.value) : [...arr, o.value])}
            className={`rounded-full border px-3 py-1 text-xs transition-colors ${on ? "bg-primary text-primary-foreground border-primary" : "hover:bg-muted"}`}>{o.label}</button>;
        })}
      </div>
    );
  }
  if (f.type === "custom") return f.render({ value, set, form });
  return <Input type={f.type || "text"} value={value ?? ""} min={f.min} max={f.max} step={f.step} onChange={(e) => set(f.type === "number" ? (e.target.value === "" ? "" : Number(e.target.value)) : e.target.value)} placeholder={f.placeholder} data-testid={tid} />;
}

export function FormDialog({ open, onOpenChange, title, description, fields, initial, onSubmit, submitLabel = "Save", wide, testid = "form-dialog" }) {
  const [form, setForm] = useState(initial || {});
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) { setForm(initial || {}); setErrors({}); } }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async (e) => {
    e.preventDefault();
    const errs = {};
    fields.forEach((f) => {
      if (f.hidden?.(form)) return;
      const v = form[f.name];
      if (f.required && (v === undefined || v === null || v === "" || (Array.isArray(v) && !v.length))) errs[f.name] = `${f.label} is required`;
      if (f.type === "email" && v && !/^\S+@\S+\.\S+$/.test(v)) errs[f.name] = "Enter a valid email";
      if (f.validate && !errs[f.name]) { const m = f.validate(v, form); if (m) errs[f.name] = m; }
    });
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    try { await onSubmit(form); onOpenChange(false); }
    catch (er) { toast.error(errMsg(er)); }
    finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={`${wide ? "sm:max-w-3xl" : "sm:max-w-lg"} max-h-[90vh] overflow-y-auto`} data-testid={testid}>
        <DialogHeader><DialogTitle className="font-display">{title}</DialogTitle>{description && <DialogDescription>{description}</DialogDescription>}</DialogHeader>
        <form onSubmit={submit} className="space-y-4" noValidate>
          <div className={`grid gap-4 ${wide ? "sm:grid-cols-2" : ""}`}>
            {fields.filter((f) => !f.hidden?.(form)).map((f) => (
              <div key={f.name} className={`space-y-1.5 ${f.full ? "sm:col-span-2" : ""}`}>
                <Label className="text-xs font-semibold">{f.label}{f.required && <span className="text-rose-500"> *</span>}</Label>
                <FieldInput f={f} form={form} value={form[f.name]} set={(v) => setForm((p) => ({ ...p, [f.name]: v, ...(f.onChange ? f.onChange(v, p) : {}) }))} />
                {f.help && <p className="text-[11px] text-muted-foreground">{f.help}</p>}
                {errors[f.name] && <p className="text-xs text-rose-600" data-testid={`error-${f.name}`}>{errors[f.name]}</p>}
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} data-testid={`${testid}-cancel`}>Cancel</Button>
            <Button type="submit" disabled={busy} data-testid={`${testid}-submit`}>{busy && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}{submitLabel}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
