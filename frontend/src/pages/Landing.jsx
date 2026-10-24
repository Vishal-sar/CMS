import { Link } from "react-router-dom";
import { GraduationCap, ShieldCheck, CalendarCheck, Wallet, Award, Users, NotebookPen, Bus, ArrowRight, Mail, Phone, MapPin } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/components/app/Layout";

const FEATURES = [
  { icon: Users, t: "Students & Staff", d: "Admissions, profiles, ID cards, promotions and complete enrollment history." },
  { icon: CalendarCheck, t: "Attendance", d: "Bulk marking by section, automatic percentages and low-attendance alerts." },
  { icon: Award, t: "Exams & Report Cards", d: "Marks entry, configurable grading, publishing and printable report cards." },
  { icon: Wallet, t: "Fees & Receipts", d: "Invoices, partial payments, verified online payments and printable receipts." },
  { icon: NotebookPen, t: "Homework", d: "Assignments, submissions, grading and feedback for every class." },
  { icon: Bus, t: "Library & Transport", d: "Book issues with fines, routes, stops and vehicle capacity tracking." },
];
const PORTALS = [["Administrators", "Run the whole school from one control panel."], ["Teachers", "Classes, attendance, marks and homework."], ["Students", "Timetable, results, homework and fees."], ["Parents", "Follow every child's progress and pay fees."]];

export default function Landing() {
  const { school, user } = useAuth();
  useTheme();
  const name = school?.school_name || "EduPrime International School";
  return (
    <div className="min-h-screen bg-background">
      <header className="absolute inset-x-0 top-0 z-20">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-3"><div className="h-10 w-10 rounded-xl bg-amber-400 grid place-items-center"><GraduationCap className="h-6 w-6 text-[#0A192F]" /></div>
            <span className="font-display font-bold text-white text-lg">{name}</span></div>
          <Link to={user ? "/app" : "/login"}><Button className="rounded-full bg-white text-[#0A192F] hover:bg-amber-300" data-testid="landing-login-btn">{user ? "Open dashboard" : "Portal login"}</Button></Link>
        </div>
      </header>
      <section className="relative overflow-hidden bg-[#0A192F]">
        <img src="/img/hero.jpg" alt="Students in a classroom" className="absolute inset-0 h-full w-full object-cover opacity-25" />
        <div className="absolute inset-0 bg-gradient-to-r from-[#0A192F] via-[#0A192F]/90 to-transparent" />
        <div className="relative max-w-7xl mx-auto px-6 pt-40 pb-28 grid lg:grid-cols-2 gap-12">
          <div className="fade-up">
            <p className="inline-flex items-center gap-2 rounded-full border border-amber-400/40 bg-amber-400/10 px-3 py-1 text-xs font-semibold text-amber-300"><ShieldCheck className="h-3.5 w-3.5" />Secure role-based school platform</p>
            <h1 className="mt-6 text-4xl sm:text-5xl lg:text-6xl font-extrabold text-white leading-[1.05]">Every class, record and rupee — <span className="text-amber-400">in one place.</span></h1>
            <p className="mt-6 text-base text-slate-300 max-w-xl">{name} runs admissions, attendance, examinations, fees, homework and communication on a single connected system for administrators, teachers, students and parents.</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/login"><Button size="lg" className="rounded-full bg-amber-400 text-[#0A192F] hover:bg-amber-300" data-testid="hero-cta-login">Sign in to your portal <ArrowRight className="h-4 w-4 ml-2" /></Button></Link>
              <a href="#features"><Button size="lg" variant="outline" className="rounded-full border-white/30 bg-transparent text-white hover:bg-white/10" data-testid="hero-cta-features">Explore features</Button></a>
            </div>
          </div>
          <div className="hidden lg:grid grid-cols-2 gap-4 self-end">
            {PORTALS.map(([t, d], i) => (
              <div key={t} className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-5 fade-up" style={{ animationDelay: `${i * 90}ms` }}>
                <p className="font-display font-semibold text-white">{t}</p><p className="text-sm text-slate-300 mt-1">{d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
      <section id="features" className="max-w-7xl mx-auto px-6 py-24">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-sky-600">Modules</p>
        <h2 className="text-3xl sm:text-4xl font-bold mt-2 max-w-2xl">Built for the real day-to-day of a school.</h2>
        <div className="mt-12 grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((f) => (
            <div key={f.t} className="card-surface p-6 hover:-translate-y-0.5 transition-transform">
              <div className="h-11 w-11 rounded-xl bg-sky-100 dark:bg-sky-500/15 grid place-items-center"><f.icon className="h-5 w-5 text-sky-700 dark:text-sky-300" /></div>
              <h3 className="mt-4 font-semibold text-lg">{f.t}</h3><p className="text-sm text-muted-foreground mt-1">{f.d}</p>
            </div>
          ))}
        </div>
      </section>
      <section className="max-w-7xl mx-auto px-6 pb-24 grid lg:grid-cols-2 gap-10 items-center">
        <img src="/img/teacher.jpg" alt="Teacher with students" className="rounded-2xl object-cover w-full h-80" />
        <div>
          <h2 className="text-3xl font-bold">Privacy and accountability by design</h2>
          <ul className="mt-6 space-y-3 text-sm text-muted-foreground">
            {["Parents see only their own children's records", "Teachers access only their assigned classes and subjects", "Every sensitive change is recorded in the audit trail", "Online payments are confirmed with the gateway before invoices update"].map((x) => (
              <li key={x} className="flex gap-3"><ShieldCheck className="h-5 w-5 text-amber-500 shrink-0" />{x}</li>))}
          </ul>
        </div>
      </section>
      <footer className="bg-[#0A192F] text-slate-300">
        <div className="max-w-7xl mx-auto px-6 py-12 grid md:grid-cols-3 gap-8 text-sm">
          <div><p className="font-display font-bold text-white text-lg">{name}</p><p className="mt-2 text-slate-400">{school?.tagline}</p></div>
          <div className="space-y-2">
            <p className="flex gap-2"><MapPin className="h-4 w-4 text-amber-400" />{school?.address}</p>
            <p className="flex gap-2"><Phone className="h-4 w-4 text-amber-400" />{school?.phone}</p>
            <p className="flex gap-2"><Mail className="h-4 w-4 text-amber-400" />{school?.email}</p>
          </div>
          <div className="md:text-right text-slate-400">© {new Date().getFullYear()} {name}. All rights reserved.</div>
        </div>
      </footer>
    </div>
  );
}
