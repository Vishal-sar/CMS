import { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { Plus, Printer, Receipt, CreditCard, Sparkles, Ban, Undo2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import CrudPage from "@/components/app/CrudPage";
import { FormDialog, SelectField } from "@/components/app/FormDialog";
import { DataTable, SearchInput, useTableState } from "@/components/app/DataTable";
import { useFetch, useOptions, PageHeader, Section, Badge, Loading, Confirm, StatCard } from "@/components/app/common";
import { api, errMsg, downloadFile, fileUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { inr, fdate, todayISO } from "@/lib/fmt";

const loadScript = (src) => new Promise((res, rej) => { if (document.querySelector(`script[src="${src}"]`)) return res(); const s = document.createElement("script"); s.src = src; s.onload = res; s.onerror = rej; document.body.appendChild(s); });

function PayOnline({ inv, onDone }) {
  const { data: cfg } = useFetch("/payments-config"); const [busy, setBusy] = useState(""); const [amt, setAmt] = useState(inv.balance);
  const rzp = async () => {
    setBusy("rzp");
    try {
      await loadScript("https://checkout.razorpay.com/v1/checkout.js");
      const { data: o } = await api.post("/payments/razorpay/order", { invoice_id: inv.id, amount: amt });
      new window.Razorpay({ key: o.key_id, order_id: o.order_id, amount: o.amount, currency: "INR", name: "School fee", description: o.invoice_no,
        handler: async (r) => { const { data } = await api.post("/payments/razorpay/verify", r); data.status === "paid" ? toast.success(`Payment verified. Receipt ${data.receipt_no}`) : toast.info(data.message); onDone(); },
        modal: { ondismiss: () => setBusy("") } }).open();
    } catch (e) { toast.error(errMsg(e)); setBusy(""); }
  };
  const cf = async () => {
    setBusy("cf");
    try {
      await loadScript("https://sdk.cashfree.com/js/v3/cashfree.js");
      const { data: o } = await api.post("/payments/cashfree/order", { invoice_id: inv.id, amount: amt, origin_url: window.location.origin });
      await window.Cashfree({ mode: cfg.cashfree_mode }).checkout({ paymentSessionId: o.payment_session_id, redirectTarget: "_self" });
    } catch (e) { toast.error(errMsg(e)); setBusy(""); }
  };
  if (!cfg) return null;
  if (!cfg.razorpay && !cfg.cashfree) return <p className="text-xs text-muted-foreground" data-testid="online-payment-unavailable">Online payment is not available yet — the school has not configured a payment gateway. Please pay at the school office.</p>;
  return (<div className="space-y-3"><div className="flex items-center gap-2"><span className="text-sm">Amount</span><Input type="number" value={amt} max={inv.balance} min={1} onChange={(e) => setAmt(Number(e.target.value))} className="w-36" data-testid="pay-amount-input" /></div>
    <div className="flex gap-2">{cfg.razorpay && <Button onClick={rzp} disabled={!!busy || amt <= 0 || amt > inv.balance} data-testid="pay-razorpay-btn">{busy === "rzp" && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}Pay with Razorpay</Button>}
      {cfg.cashfree && <Button variant="outline" onClick={cf} disabled={!!busy || amt <= 0 || amt > inv.balance} data-testid="pay-cashfree-btn">{busy === "cf" && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}Pay with Cashfree</Button>}</div>
    <p className="text-[11px] text-muted-foreground">Your invoice updates only after the gateway confirms the payment.</p></div>);
}

function InvoiceDialog({ id, onClose, reload }) {
  const { user } = useAuth(); const { data: inv, reload: r2 } = useFetch(id ? `/invoices/${id}` : null); const { data: st } = useFetch("/settings");
  const [pay, setPay] = useState(false); const [adj, setAdj] = useState(false); const [rc, setRc] = useState(null);
  const refresh = () => { r2(); reload(); };
  const act = async (body, msg) => { try { await api.post(`/invoices/${id}/adjust`, body); toast.success(msg); refresh(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <Dialog open={!!id} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="invoice-dialog">
        {!inv ? <Loading /> : <>
          <DialogHeader><DialogTitle className="flex items-center gap-3">{inv.invoice_no} <Badge value={inv.display_status} testid="invoice-status" /></DialogTitle></DialogHeader>
          <p className="text-sm">{inv.student_name} · {inv.admission_no} · {inv.class_name}-{inv.section} · Due {fdate(inv.due_date)}</p>
          <div className="rounded-lg border divide-y text-sm">{inv.items.map((i, k) => <div key={k} className="flex justify-between p-2"><span>{i.name}</span><span>{inr(i.amount)}</span></div>)}
            {inv.discount > 0 && <div className="flex justify-between p-2 text-emerald-700"><span>Discount {inv.discount_reason && `(${inv.discount_reason})`}</span><span>-{inr(inv.discount)}</span></div>}
            {inv.late_fee > 0 && <div className="flex justify-between p-2 text-rose-700"><span>Late fee</span><span>{inr(inv.late_fee)}</span></div>}
            <div className="flex justify-between p-2 font-bold"><span>Total</span><span>{inr(inv.total)}</span></div>
            <div className="flex justify-between p-2"><span>Paid</span><span>{inr(inv.paid)}</span></div><div className="flex justify-between p-2 font-bold"><span>Balance</span><span data-testid="invoice-balance">{inr(inv.balance)}</span></div></div>
          {inv.payments.length > 0 && <div><p className="font-semibold text-sm mb-2">Payments</p>{inv.payments.map((p) => <div key={p.id} className="flex items-center justify-between text-sm py-1.5 border-b">
            <span>{p.receipt_no} · {fdate(p.date)} · {p.method}</span><span className="flex items-center gap-2">{inr(p.amount)}<Badge value={p.status} />
              <Button size="sm" variant="ghost" onClick={() => setRc(p.id)} data-testid={`receipt-${p.id}`}><Receipt className="h-4 w-4" /></Button>
              {user.role === "admin" && p.status === "success" && <Confirm title="Mark this payment as refunded?" description="The invoice balance will increase. Gateway refunds must also be issued in the provider dashboard." onConfirm={() => api.post(`/payments/${p.id}/refund`).then(() => { toast.success("Refunded"); refresh(); }).catch((e) => toast.error(errMsg(e)))}
                trigger={<Button size="sm" variant="ghost" data-testid={`refund-${p.id}`}><Undo2 className="h-4 w-4" /></Button>} />}</span></div>)}</div>}
          {inv.balance > 0 && inv.status !== "void" && (user.role === "admin" ? <div className="flex flex-wrap gap-2">
            <Button onClick={() => setPay(true)} data-testid="record-payment-btn"><CreditCard className="h-4 w-4 mr-2" />Record payment</Button>
            <Button variant="outline" onClick={() => setAdj(true)} data-testid="discount-btn">Discount / scholarship</Button>
            {inv.display_status === "overdue" && !inv.late_fee && <Confirm title="Apply late fee?" description={`A late fee of ${inr(st?.late_fee_amount)} will be added per school policy.`} destructive={false} onConfirm={() => act({ apply_late_fee: true }, "Late fee applied")} trigger={<Button variant="outline" data-testid="late-fee-btn">Apply late fee</Button>} />}
            {inv.paid === 0 && <Confirm title="Void this invoice?" onConfirm={() => act({ void: true }, "Invoice voided")} trigger={<Button variant="outline" className="text-rose-600" data-testid="void-invoice-btn"><Ban className="h-4 w-4 mr-1" />Void</Button>} />}
          </div> : <PayOnline inv={inv} onDone={refresh} />)}
          <FormDialog open={pay} onOpenChange={setPay} title="Record payment" testid="payment-form" initial={{ amount: inv.balance, date: todayISO(), method: "Cash" }}
            fields={[{ name: "amount", label: `Amount (balance ${inr(inv.balance)})`, type: "number", required: true, validate: (v) => (v <= 0 || v > inv.balance ? "Amount must be between 1 and the balance" : null) },
              { name: "method", label: "Method", type: "select", required: true, options: (st?.payment_methods || ["Cash"]).map((m) => ({ value: m, label: m })) },
              { name: "date", label: "Payment date", type: "date", required: true }, { name: "reference", label: "Reference / transaction no." }]}
            onSubmit={async (f) => { const { data } = await api.post("/payments", { ...f, invoice_id: inv.id }); toast.success(`Payment recorded. Receipt ${data.receipt_no}`); refresh(); setRc(data.id); }} />
          <FormDialog open={adj} onOpenChange={setAdj} title="Discount / scholarship" testid="discount-form" initial={{ discount: inv.discount, discount_reason: inv.discount_reason }}
            fields={[{ name: "discount", label: "Discount amount (₹)", type: "number", required: true }, { name: "discount_reason", label: "Reason / scholarship", required: true }]} onSubmit={(f) => act(f, "Discount updated")} />
          <ReceiptView id={rc} onClose={() => setRc(null)} />
        </>}
      </DialogContent>
    </Dialog>
  );
}

export function ReceiptView({ id, onClose }) {
  const { data } = useFetch(id ? `/payments/${id}/receipt` : null);
  return (
    <Dialog open={!!id} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-lg">{!data ? <Loading /> : <>
        <div className="print-area bg-white text-[#0A192F] p-6 rounded-lg border" data-testid="receipt-view">
          <div className="flex items-center gap-3 border-b-2 border-amber-400 pb-3">{data.school.logo_file_id && <img src={fileUrl(data.school.logo_file_id)} alt="" className="h-12 w-12 object-contain" />}
            <div><p className="font-bold text-lg">{data.school.school_name}</p><p className="text-[11px]">{data.school.address} · {data.school.phone}</p></div></div>
          <p className="text-center font-bold tracking-widest text-sky-700 my-3">FEE RECEIPT</p>
          <div className="grid grid-cols-2 gap-1 text-sm"><p>Receipt: <b>{data.payment.receipt_no}</b></p><p>Date: {fdate(data.payment.date)}</p><p>Student: <b>{data.payment.student_name}</b></p><p>Adm. No: {data.payment.admission_no}</p>
            <p>Class: {data.invoice.class_name}-{data.invoice.section}</p><p>Invoice: {data.invoice.invoice_no}</p><p>Method: {data.payment.method}</p><p>Ref: {data.payment.reference || "—"}</p></div>
          <div className="my-4 rounded-lg bg-slate-50 p-4 flex justify-between font-bold"><span>Amount received</span><span>{inr(data.payment.amount)}</span></div>
          <p className="text-xs">Invoice total {inr(data.invoice.total)} · Paid to date {inr(data.invoice.paid)} · Balance {inr(data.invoice.balance)}</p>
          {data.payment.status !== "success" && <p className="text-rose-600 font-bold mt-2 uppercase">{data.payment.status}</p>}
          <div className="flex justify-between mt-10 text-xs"><span>{data.school.receipt_footer}</span><span className="border-t px-6 pt-1">Authorised signatory</span></div></div>
        <Button onClick={() => window.print()} data-testid="print-receipt-btn"><Printer className="h-4 w-4 mr-2" />Print receipt</Button></>}</DialogContent>
    </Dialog>
  );
}

function Invoices() {
  const { user, childId } = useAuth(); const { classes } = useOptions(); const t = useTableState();
  const sf = user.role === "parent" ? { student_id: childId } : {};
  const { data, loading, error, reload } = useFetch("/invoices", { q: t.q, page: t.page, ...t.filters, ...sf }, [childId]);
  const [open, setOpen] = useState(null); const [gen, setGen] = useState(false); const [adhoc, setAdhoc] = useState(false);
  const fs = useFetch(user.role === "admin" ? "/fee-structures" : null, { page_size: 100 }); const studs = useFetch(user.role === "admin" ? "/students" : null, { page_size: 500, sort: "name" });
  const cols = [{ key: "invoice_no", label: "Invoice", render: (r) => <span><b>{r.invoice_no}</b><span className="block text-xs text-muted-foreground">{r.items.map((i) => i.name).join(", ")}</span></span> },
    { key: "student_name", label: "Student", render: (r) => <span>{r.student_name}<span className="block text-xs text-muted-foreground">{r.class_name}-{r.section}</span></span> },
    { key: "total", label: "Total", render: (r) => inr(r.total) }, { key: "balance", label: "Balance", render: (r) => <b>{inr(r.balance)}</b> }, { key: "due_date", label: "Due", render: (r) => fdate(r.due_date) },
    { key: "display_status", label: "Status", render: (r) => <Badge value={r.display_status} /> }];
  return (
    <Section action={user.role === "admin" && <div className="flex gap-2"><Button variant="outline" onClick={() => setAdhoc(true)} data-testid="adhoc-invoice-btn"><Plus className="h-4 w-4 mr-1" />Invoice</Button><Button onClick={() => setGen(true)} data-testid="generate-invoices-btn"><Sparkles className="h-4 w-4 mr-1" />Generate from fee structure</Button></div>}>
      <div className="flex flex-col sm:flex-row gap-3 mb-4">{user.role === "admin" && <SearchInput value={t.q} onChange={t.setSearch} placeholder="Invoice no, student…" testid="invoice-search" />}
        <div className="w-40"><SelectField value={t.filters.status || ""} onChange={(v) => t.setFilter("status", v)} allowEmpty="All statuses" options={["unpaid", "partial", "paid", "overdue"].map((s) => ({ value: s, label: s }))} testid="invoice-status-filter" /></div>
        {user.role === "admin" && <div className="w-40"><SelectField value={t.filters.class_id || ""} onChange={(v) => t.setFilter("class_id", v)} allowEmpty="All classes" options={classes.map((c) => ({ value: c.id, label: c.name }))} testid="invoice-class-filter" /></div>}</div>
      <DataTable columns={cols} rows={data?.items} loading={loading} error={error} onRetry={reload} page={t.page} total={data?.total} onPage={t.setPage} onRowClick={(r) => setOpen(r.id)} testid="invoices-table" />
      <InvoiceDialog id={open} onClose={() => setOpen(null)} reload={reload} />
      <FormDialog open={gen} onOpenChange={setGen} title="Generate invoices" description="Creates one invoice per active student. Students who already have an invoice for this structure are skipped." testid="generate-form"
        fields={[{ name: "structure_id", label: "Fee structure", type: "select", required: true, options: (fs.data?.items || []).map((f) => ({ value: f.id, label: `${f.name} · ${inr(f.amount)} · due ${fdate(f.due_date)}` })) }, { name: "section", label: "Only section (optional)" }]}
        onSubmit={async (f) => { const { data } = await api.post("/invoices/generate", f); toast.success(`${data.created} invoices created, ${data.skipped_existing} skipped`); reload(); }} />
      <FormDialog open={adhoc} onOpenChange={setAdhoc} title="New invoice" testid="adhoc-form" initial={{ due_date: todayISO(), discount: 0 }}
        fields={[{ name: "student_id", label: "Student", type: "select", required: true, options: (studs.data?.items || []).map((s) => ({ value: s.id, label: `${s.name} (${s.admission_no})` })) },
          { name: "item", label: "Description", required: true }, { name: "amount", label: "Amount (₹)", type: "number", required: true, validate: (v) => (v <= 0 ? "Must be positive" : null) }, { name: "due_date", label: "Due date", type: "date", required: true }]}
        onSubmit={async (f) => { await api.post("/invoices", { student_id: f.student_id, items: [{ name: f.item, amount: f.amount }], due_date: f.due_date, discount: 0 }); toast.success("Invoice created"); reload(); }} />
    </Section>
  );
}

function Payments() {
  const t = useTableState(); const { data, loading, reload } = useFetch("/payments", { q: t.q, page: t.page, ...t.filters }); const [rc, setRc] = useState(null);
  return (
    <Section action={<Button variant="outline" onClick={() => downloadFile("/reports/transactions", { format: "csv", date_from: t.filters.date_from, date_to: t.filters.date_to, method: t.filters.method }, "transactions.csv")} data-testid="export-payments-btn">Export CSV</Button>}>
      <div className="flex flex-wrap gap-3 mb-4"><SearchInput value={t.q} onChange={t.setSearch} placeholder="Receipt, student…" testid="payment-search" />
        <div className="w-40"><SelectField value={t.filters.method || ""} onChange={(v) => t.setFilter("method", v)} allowEmpty="All methods" options={["Cash", "Bank Transfer", "Card", "UPI", "Cheque", "Online (Razorpay)", "Online (Cashfree)"].map((m) => ({ value: m, label: m }))} testid="payment-method-filter" /></div>
        <Input type="date" className="w-40" value={t.filters.date_from || ""} onChange={(e) => t.setFilter("date_from", e.target.value)} data-testid="payment-from" /><Input type="date" className="w-40" value={t.filters.date_to || ""} onChange={(e) => t.setFilter("date_to", e.target.value)} data-testid="payment-to" />
        <span className="self-center text-sm">Total: <b data-testid="payments-sum">{inr(data?.sum)}</b></span></div>
      <DataTable loading={loading} rows={data?.items} page={t.page} total={data?.total} onPage={t.setPage} onRowClick={(r) => setRc(r.id)} testid="payments-table" columns={[{ key: "receipt_no", label: "Receipt" }, { key: "date", label: "Date", render: (r) => fdate(r.date) },
        { key: "student_name", label: "Student" }, { key: "invoice_no", label: "Invoice" }, { key: "method", label: "Method" }, { key: "amount", label: "Amount", render: (r) => <b>{inr(r.amount)}</b> }, { key: "status", label: "Status", render: (r) => <Badge value={r.status} /> }]} />
      <ReceiptView id={rc} onClose={() => { setRc(null); reload(); }} />
    </Section>
  );
}

function Structures() {
  const { classes } = useOptions(); const { data: st } = useFetch("/settings");
  return <CrudPage hideHeader title="Fee Structures" endpoint="/fee-structures" testid="fee-structures" defaults={{ class_id: "all", academic_year: st?.academic_year, installment: "Full", fee_type: "Tuition" }}
    fields={[{ name: "name", label: "Name", required: true }, { name: "fee_type", label: "Fee type", type: "select", required: true, options: ["Tuition", "Admission", "Examination", "Transport", "Activity", "Library", "Other"].map((v) => ({ value: v, label: v })) },
      { name: "class_id", label: "Class", type: "select", options: [{ value: "all", label: "All classes" }, ...classes.map((c) => ({ value: c.id, label: c.name }))] }, { name: "academic_year", label: "Academic year", required: true },
      { name: "amount", label: "Amount (₹)", type: "number", required: true, validate: (v) => (v <= 0 ? "Must be positive" : null) }, { name: "due_date", label: "Due date", type: "date", required: true }, { name: "installment", label: "Installment / schedule" }]}
    columns={[{ key: "name", label: "Name", render: (r) => <b>{r.name}</b> }, { key: "fee_type", label: "Type" }, { key: "class_id", label: "Class", render: (r) => (r.class_id === "all" ? "All" : classes.find((c) => c.id === r.class_id)?.name) },
      { key: "amount", label: "Amount", render: (r) => inr(r.amount) }, { key: "due_date", label: "Due", render: (r) => fdate(r.due_date) }, { key: "installment", label: "Schedule" }]} />;
}

export default function Fees() {
  const { user } = useAuth(); const { data: d } = useFetch(user.role === "admin" ? "/dashboard" : null); const [sending, setSending] = useState(false);
  const remind = async () => { setSending(true); try { const { data: r } = await api.post("/fees/send-reminders"); r.skipped ? toast.info("Fee reminders are turned off in Settings") : toast.success(`Reminders: ${r.due_soon} due soon, ${r.overdue} overdue · ${r.emails_sent} emails sent${r.emails_failed ? `, ${r.emails_failed} failed` : ""}`); } catch (e) { toast.error(errMsg(e)); } finally { setSending(false); } };
  return (
    <div className="page" data-testid="fees-page">
      <PageHeader title="Fees & Payments" subtitle={user.role === "admin" ? "Invoices, collections, receipts and fee structures. Reminder emails go out automatically every day at 9 AM." : "Invoices, payment history and receipts"}
        actions={user.role === "admin" && <Button variant="outline" onClick={remind} disabled={sending} data-testid="send-reminders-btn">{sending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}Send fee reminders now</Button>} />
      {d && <div className="grid grid-cols-1 sm:grid-cols-3 gap-4"><StatCard label="Collected" value={inr(d.stats.fees_collected)} tone="green" /><StatCard label="Outstanding" value={inr(d.stats.fees_pending)} tone="gold" /><StatCard label="Overdue" value={inr(d.stats.fees_overdue)} tone="red" /></div>}
      {user.role === "admin" ? <Tabs defaultValue="invoices"><TabsList><TabsTrigger value="invoices">Invoices</TabsTrigger><TabsTrigger value="payments" data-testid="tab-payments">Payments</TabsTrigger><TabsTrigger value="structures" data-testid="tab-structures">Fee structures</TabsTrigger></TabsList>
        <TabsContent value="invoices"><Invoices /></TabsContent><TabsContent value="payments"><Payments /></TabsContent><TabsContent value="structures"><Structures /></TabsContent></Tabs> : <Invoices />}
    </div>
  );
}

export function PaymentResult() {
  const [sp] = useSearchParams(); const oid = sp.get("order_id"); const [s, setS] = useState(null); const [n, setN] = useState(0);
  useEffect(() => {
    if (!oid) return;
    api.get(`/payments/order-status/${oid}`).then((r) => { setS(r.data); if (r.data.status !== "paid" && r.data.status !== "failed" && n < 8) setTimeout(() => setN(n + 1), 2500); }).catch((e) => setS({ status: "error", message: errMsg(e) }));
  }, [oid, n]);
  return (
    <div className="page max-w-lg"><Section testid="payment-result">
      {!s ? <Loading label="Confirming payment with the gateway…" /> : s.status === "paid" ? <div className="text-center py-6"><p className="text-2xl font-bold text-emerald-600">Payment confirmed</p><p className="mt-2">{inr(s.amount)} · Receipt {s.receipt_no}</p></div>
        : s.status === "failed" ? <div className="text-center py-6"><p className="text-2xl font-bold text-rose-600">Payment failed</p><p className="mt-2 text-sm">No money was recorded against your invoice.</p></div>
        : <div className="text-center py-6"><p className="text-xl font-bold text-amber-600">Payment pending</p><p className="mt-2 text-sm">{s.message || "We haven't received confirmation from the gateway yet. Your invoice will update once it is verified."}</p></div>}
      <div className="text-center"><Link to="/app/fees"><Button variant="outline" data-testid="back-to-fees">Back to fees</Button></Link></div></Section></div>
  );
}
