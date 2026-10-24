import { Link, useNavigate } from "react-router-dom";
import { GraduationCap, Users, UsersRound, School, UserCheck, UserX, Percent, Wallet, AlertCircle, FileText, UserPlus, CalendarCheck, Receipt, Megaphone, BarChart3, BookOpen, Clock, NotebookPen } from "lucide-react";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, BarChart, Bar, PieChart, Pie, Cell, Legend } from "recharts";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { inr, fdate, fdatetime, titleCase } from "@/lib/fmt";
import { useFetch, StatCard, Section, Loading, ErrorBox, Empty, Badge, PageHeader, DemoNote } from "@/components/app/common";

const C = ["hsl(var(--chart-1))", "hsl(var(--chart-2))", "hsl(var(--chart-3))", "hsl(var(--chart-4))", "hsl(var(--chart-5))"];
const tip = { contentStyle: { background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: 10, fontSize: 12 } };

function AdminDash({ d }) {
  const s = d.stats; const nav = useNavigate();
  const qa = [["Add Student", UserPlus, "/app/admissions"], ["Add Teacher", Users, "/app/teachers"], ["Add Parent", UsersRound, "/app/parents"], ["Create Class", School, "/app/classes"],
    ["Mark Attendance", CalendarCheck, "/app/attendance"], ["Create Exam", FileText, "/app/exams"], ["Generate Report", BarChart3, "/app/reports"], ["Record Payment", Receipt, "/app/fees"], ["Publish Notice", Megaphone, "/app/announcements"]];
  return (
    <>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard icon={GraduationCap} label="Total Students" value={s.students} hint={`${s.parents} parents linked`} testid="stat-students" />
        <StatCard icon={Users} label="Teachers" value={s.teachers} hint={`${s.classes} classes · ${s.sections} sections`} tone="sky" testid="stat-teachers" />
        <StatCard icon={Percent} label="Attendance Today" value={s.attendance_pct != null ? `${s.attendance_pct}%` : "Not marked"} hint={`${s.present_today} present · ${s.absent_today} absent`} tone="green" testid="stat-attendance" />
        <StatCard icon={Wallet} label="Fees Collected" value={inr(s.fees_collected)} hint={`${inr(s.fees_pending)} pending · ${inr(s.fees_overdue)} overdue`} tone="gold" testid="stat-fees" />
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={UserCheck} label="Present Today" value={s.present_today} tone="green" testid="stat-present" />
        <StatCard icon={UserX} label="Absent Today" value={s.absent_today} tone="red" testid="stat-absent" />
        <StatCard icon={FileText} label="Upcoming Exams" value={s.upcoming_exams} tone="sky" testid="stat-exams" />
        <StatCard icon={AlertCircle} label="Pending Leaves" value={s.pending_leaves} hint={`${s.overdue_books} overdue books`} tone="gold" testid="stat-leaves" />
      </div>
      <Section title="Quick actions" testid="quick-actions">
        <div className="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-9 gap-2">
          {qa.map(([l, I, to]) => <button key={l} onClick={() => nav(to)} className="flex flex-col items-center gap-2 rounded-xl border p-3 text-xs font-medium hover:border-amber-400 hover:bg-amber-50/50 dark:hover:bg-amber-500/5 transition-colors" data-testid={`quick-${l.toLowerCase().replace(/\s/g, "-")}`}><I className="h-5 w-5 text-sky-600" />{l}</button>)}
        </div>
      </Section>
      <div className="grid lg:grid-cols-3 gap-4">
        <Section title="Attendance trend (last 3 weeks)" className="lg:col-span-2">
          {d.attendance_trend.length ? <ResponsiveContainer width="100%" height={240}><AreaChart data={d.attendance_trend}><defs><linearGradient id="g1" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="hsl(var(--chart-2))" stopOpacity={0.35} /><stop offset="100%" stopColor="hsl(var(--chart-2))" stopOpacity={0} /></linearGradient></defs>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" /><XAxis dataKey="date" fontSize={11} /><YAxis domain={[50, 100]} fontSize={11} unit="%" /><Tooltip {...tip} /><Area dataKey="percentage" name="Attendance %" stroke="hsl(var(--chart-2))" fill="url(#g1)" strokeWidth={2} /></AreaChart></ResponsiveContainer> : <Empty title="No attendance yet" />}
        </Section>
        <Section title="Fee collection vs outstanding">
          <ResponsiveContainer width="100%" height={240}><PieChart><Pie data={d.fee_split} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={3}>{d.fee_split.map((_, i) => <Cell key={i} fill={[C[0], C[2]][i]} />)}</Pie><Tooltip {...tip} formatter={(v) => inr(v)} /><Legend /></PieChart></ResponsiveContainer>
        </Section>
      </div>
      <div className="grid lg:grid-cols-3 gap-4">
        <Section title="Enrollment by month"><ResponsiveContainer width="100%" height={220}><BarChart data={d.enrollment}><CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" /><XAxis dataKey="month" fontSize={10} /><YAxis fontSize={11} allowDecimals={false} /><Tooltip {...tip} /><Bar dataKey="students" fill={C[0]} radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></Section>
        <Section title="Class-wise students"><ResponsiveContainer width="100%" height={220}><BarChart data={d.class_distribution}><CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" /><XAxis dataKey="class" fontSize={10} /><YAxis fontSize={11} allowDecimals={false} /><Tooltip {...tip} /><Bar dataKey="students" fill={C[1]} radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></Section>
        <Section title="Exam performance (avg %)">{d.exam_performance.length ? <ResponsiveContainer width="100%" height={220}><BarChart data={d.exam_performance} layout="vertical"><XAxis type="number" domain={[0, 100]} fontSize={11} /><YAxis type="category" dataKey="exam" width={110} fontSize={9} /><Tooltip {...tip} /><Bar dataKey="average" fill={C[2]} radius={[0, 6, 6, 0]} /></BarChart></ResponsiveContainer> : <Empty title="No published results" />}</Section>
      </div>
      <div className="grid lg:grid-cols-3 gap-4">
        <Section title="Recent admissions" action={<Link to="/app/students" className="text-xs text-sky-600">View all</Link>}>
          <div className="space-y-3">{d.recent_admissions.map((r) => <Link to={`/app/students/${r.id}`} key={r.id} className="flex justify-between text-sm hover:text-sky-600"><span className="truncate">{r.name}<span className="block text-xs text-muted-foreground">{r.admission_no} · {r.class_name}-{r.section}</span></span><span className="text-xs text-muted-foreground">{fdate(r.admission_date)}</span></Link>)}</div>
        </Section>
        <Section title="Recent payments" action={<Link to="/app/fees" className="text-xs text-sky-600">View all</Link>}>
          <div className="space-y-3">{d.recent_payments.map((p) => <div key={p.id} className="flex justify-between text-sm"><span className="truncate">{p.student_name}<span className="block text-xs text-muted-foreground">{p.receipt_no} · {p.method}</span></span><span className="font-semibold">{inr(p.amount)}</span></div>)}</div>
        </Section>
        <Section title="Upcoming exams & events">
          <div className="space-y-3">{d.upcoming_exams.map((e) => <div key={e.exam_id} className="flex justify-between text-sm"><span>{e.exam}<span className="block text-xs text-muted-foreground">{e.class_name}</span></span><span className="text-xs">{fdate(e.date)}</span></div>)}
            {d.events.map((e) => <div key={e.id} className="flex justify-between text-sm"><span>{e.title}<span className="block text-xs text-muted-foreground capitalize">{e.type}</span></span><span className="text-xs">{fdate(e.start_date)}</span></div>)}</div>
        </Section>
      </div>
      <Section title="Recent activity" action={<Link to="/app/audit" className="text-xs text-sky-600">Audit log</Link>}>
        <div className="divide-y">{d.activity.map((a) => <div key={a.id} className="py-2 flex justify-between text-sm gap-3"><span><b>{a.user_name}</b> {titleCase(a.action)} · <span className="text-muted-foreground">{a.entity}</span></span><span className="text-xs text-muted-foreground whitespace-nowrap">{fdatetime(a.created_at)}</span></div>)}</div>
      </Section>
    </>
  );
}

function TeacherDash({ d }) {
  return (
    <>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={School} label="My Sections" value={d.sections.length} testid="stat-sections" />
        <StatCard icon={BookOpen} label="Subjects taught" value={d.subjects} tone="sky" />
        <StatCard icon={Clock} label="Periods today" value={d.today_schedule.length} tone="gold" />
        <StatCard icon={NotebookPen} label="Active homework" value={d.homework.length} tone="green" />
      </div>
      <div className="grid lg:grid-cols-2 gap-4">
        <Section title="My classes" testid="teacher-sections">
          {d.sections.length ? <div className="space-y-2">{d.sections.map((s) => <div key={s.class_id + s.section} className="flex items-center justify-between rounded-lg border p-3 text-sm">
            <span><b>{s.class_name}-{s.section}</b><span className="block text-xs text-muted-foreground">{s.students} students</span></span>
            {s.marked_today ? <Badge value="present" label="Attendance marked" /> : <Link to="/app/attendance"><Button size="sm" variant="outline" data-testid={`mark-attendance-${s.class_id}-${s.section}`}>Mark attendance</Button></Link>}</div>)}</div> : <Empty title="No classes assigned yet" hint="Ask the administrator to assign you to sections." />}
        </Section>
        <Section title="Today's schedule">
          {d.today_schedule.length ? <div className="space-y-2">{d.today_schedule.map((p) => <div key={p.id} className="flex justify-between rounded-lg bg-muted/50 p-3 text-sm"><span>Period {p.period_no} · <b>{p.subject_name}</b></span><span className="text-muted-foreground">{p.class_name}-{p.section} · Room {p.room}</span></div>)}</div> : <Empty title="No periods today" />}
        </Section>
      </div>
      <Section title="My homework">{d.homework.length ? <div className="divide-y">{d.homework.map((h) => <div key={h.id} className="py-2 flex justify-between text-sm"><span>{h.title}<span className="block text-xs text-muted-foreground">Due {fdate(h.due_date)}</span></span><span className="text-xs">{h.submissions} submitted · {h.ungraded} to grade</span></div>)}</div> : <Empty title="No homework yet" />}</Section>
    </>
  );
}

function FamilyDash({ d, role }) {
  return (
    <>
      {d.children.length === 0 && <Empty title="No linked student" hint="Contact the school office to link your account." />}
      {d.children.map((c) => (
        <div key={c.student.id} className="space-y-4" data-testid={`child-card-${c.student.id}`}>
          {role === "parent" && <h3 className="font-semibold text-lg">{c.student.name} <span className="text-sm text-muted-foreground font-normal">· {c.student.class_name}-{c.student.section} · {c.student.admission_no}</span></h3>}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard icon={Percent} label="Attendance" value={c.attendance.percentage != null ? `${c.attendance.percentage}%` : "—"} hint={`Today: ${c.attendance.today ? titleCase(c.attendance.today) : "not marked"}`} tone="green" testid="stat-my-attendance" />
            <StatCard icon={UserX} label="Days absent" value={c.attendance.absent} tone="red" />
            <StatCard icon={NotebookPen} label="Homework pending" value={c.homework_pending.length} tone="sky" />
            <StatCard icon={Wallet} label="Fees due" value={inr(c.fees_due)} hint={c.overdue_invoices ? `${c.overdue_invoices} overdue` : "No overdue invoices"} tone="gold" testid="stat-fees-due" />
          </div>
          {c.homework_pending.length > 0 && <Section title="Upcoming homework"><div className="divide-y">{c.homework_pending.map((h) => <div key={h.id} className="py-2 flex justify-between text-sm"><span>{h.title}</span><span className="text-xs text-muted-foreground">Due {fdate(h.due_date)}</span></div>)}</div></Section>}
        </div>
      ))}
      <div className="grid lg:grid-cols-2 gap-4">
        <Section title="Announcements">{d.announcements.length ? <div className="space-y-3">{d.announcements.map((a) => <div key={a.id}><p className="font-medium text-sm">{a.title}</p><p className="text-xs text-muted-foreground line-clamp-2">{a.body}</p></div>)}</div> : <Empty title="No announcements" />}</Section>
        <Section title="Upcoming events">{d.events.map((e) => <div key={e.id} className="flex justify-between py-1.5 text-sm"><span>{e.title}</span><span className="text-xs text-muted-foreground">{fdate(e.start_date)}</span></div>)}</Section>
      </div>
    </>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const { data, loading, error, reload } = useFetch("/dashboard");
  const greet = new Date().getHours() < 12 ? "Good morning" : new Date().getHours() < 17 ? "Good afternoon" : "Good evening";
  return (
    <div className="page" data-testid="dashboard-page">
      <PageHeader title={`${greet}, ${user.name.split(" ")[0]}`} subtitle={<span className="flex items-center gap-2">Here's what's happening at school today. <DemoNote /></span>} />
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> :
        user.role === "admin" ? <AdminDash d={data} /> : user.role === "teacher" ? <TeacherDash d={data} /> : <FamilyDash d={data} role={user.role} />}
    </div>
  );
}
