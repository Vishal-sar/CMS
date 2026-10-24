import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate, Link } from "react-router-dom";
import { ChevronsLeft, Menu, GraduationCap, Bell, Moon, Sun, Search, LogOut, UserCircle, KeyRound, ChevronRight } from "lucide-react";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { navFor, labelForPath } from "@/lib/nav";
import { api, fileUrl } from "@/lib/api";
import { fdatetime, titleCase } from "@/lib/fmt";
import { Badge } from "./common";
import { SelectField } from "./FormDialog";

export function useTheme() {
  const [dark, setDark] = useState(() => localStorage.getItem("sms_theme") === "dark");
  useEffect(() => { document.documentElement.classList.toggle("dark", dark); localStorage.setItem("sms_theme", dark ? "dark" : "light"); }, [dark]);
  return [dark, setDark];
}

function Brand({ collapsed, className = "" }) {
  const { school } = useAuth();
  return (
    <Link to="/app" className={`flex items-center gap-3 px-4 h-16 shrink-0 ${className}`} data-testid="sidebar-brand">
      {school?.logo_file_id ? <img src={fileUrl(school.logo_file_id)} alt="logo" className="h-9 w-9 rounded-lg object-cover bg-white" />
        : <div className="h-9 w-9 rounded-lg bg-amber-400 grid place-items-center shrink-0"><GraduationCap className="h-5 w-5 text-[#0A192F]" /></div>}
      {!collapsed && <div className="min-w-0"><p className="font-display font-bold text-white text-sm leading-tight truncate">{school?.school_name || "EduPrime"}</p><p className="text-[11px] text-sky-300/80">{school?.academic_year}</p></div>}
    </Link>
  );
}

function SideNav({ collapsed, onNavigate }) {
  const { user } = useAuth();
  return (
    <nav className="flex-1 overflow-y-auto px-3 pb-6 space-y-5" data-testid="sidebar-nav">
      {navFor(user.role).map((g) => (
        <div key={g.group}>
          {!collapsed && <p className="px-3 mb-1.5 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-400/70">{g.group}</p>}
          <div className="space-y-0.5">
            {g.items.map((i) => (
              <NavLink key={i.to} to={i.to} end={i.end} onClick={onNavigate} title={i.label} data-testid={`nav-${i.to.split("/").pop() || "overview"}`}
                className={({ isActive }) => `group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${isActive ? "bg-white/10 text-white font-semibold shadow-[inset_3px_0_0_0_#F59E0B]" : "text-slate-300 hover:bg-white/5 hover:text-white"}`}>
                <i.icon className="h-[18px] w-[18px] shrink-0" />{!collapsed && <span className="truncate">{i.label}</span>}
              </NavLink>
            ))}
          </div>
        </div>
      ))}
    </nav>
  );
}

function SearchBox() {
  const [q, setQ] = useState(""); const [res, setRes] = useState([]); const [open, setOpen] = useState(false); const nav = useNavigate();
  useEffect(() => {
    if (q.trim().length < 2) { setRes([]); return; }
    const t = setTimeout(() => api.get("/search", { params: { q } }).then((r) => { setRes(r.data.results); setOpen(true); }).catch(() => {}), 250);
    return () => clearTimeout(t);
  }, [q]);
  return (
    <Popover open={open && res.length > 0} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <div className="relative hidden md:block w-80">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search students, staff, books…" className="pl-9 bg-muted/50 border-transparent focus-visible:bg-background" data-testid="global-search-input" />
        </div>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-1" align="start" onOpenAutoFocus={(e) => e.preventDefault()}>
        {res.map((r) => (
          <button key={r.type + r.id} onClick={() => { nav(`/app${r.link}`); setOpen(false); setQ(""); }} className="w-full text-left rounded-md px-3 py-2 hover:bg-muted flex items-center justify-between gap-2" data-testid={`search-result-${r.id}`}>
            <span className="min-w-0"><span className="block text-sm font-medium truncate">{r.title}</span><span className="block text-xs text-muted-foreground truncate">{r.subtitle}</span></span>
            <span className="text-[10px] uppercase text-muted-foreground">{r.type}</span>
          </button>
        ))}
      </PopoverContent>
    </Popover>
  );
}

function Notifications() {
  const [d, setD] = useState({ items: [], unread: 0 }); const nav = useNavigate();
  const load = () => api.get("/notifications").then((r) => setD(r.data)).catch(() => {});
  useEffect(() => { load(); const t = setInterval(load, 60000); return () => clearInterval(t); }, []);
  const read = async (n) => { await api.post(`/notifications/${n.id}/read`); load(); if (n.link) nav(`/app${n.link}`); };
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="relative" aria-label="Notifications" data-testid="notifications-btn">
          <Bell className="h-5 w-5" />
          {d.unread > 0 && <span className="absolute -top-0.5 -right-0.5 h-4 min-w-4 px-1 rounded-full bg-amber-500 text-[10px] font-bold text-[#0A192F] grid place-items-center" data-testid="notifications-unread-count">{d.unread}</span>}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0" data-testid="notifications-panel">
        <div className="flex items-center justify-between px-4 py-3 border-b"><p className="font-semibold text-sm">Notifications</p>
          {d.unread > 0 && <button className="text-xs text-sky-600 hover:underline" onClick={() => api.post("/notifications/all/read").then(load)} data-testid="notifications-mark-all">Mark all read</button>}</div>
        <div className="max-h-96 overflow-y-auto">
          {d.items.length === 0 && <p className="text-sm text-muted-foreground p-6 text-center">You're all caught up.</p>}
          {d.items.map((n) => (
            <button key={n.id} onClick={() => read(n)} className={`w-full text-left px-4 py-3 border-b last:border-0 hover:bg-muted/60 ${n.read ? "" : "bg-sky-50/70 dark:bg-sky-500/5"}`} data-testid={`notification-${n.id}`}>
              <p className="text-sm font-medium flex items-center gap-2">{!n.read && <span className="h-2 w-2 rounded-full bg-sky-500 shrink-0" />}{n.title}</p>
              {n.body && <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{n.body}</p>}
              <p className="text-[10px] text-muted-foreground mt-1">{fdatetime(n.created_at)}</p>
            </button>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}

function ChildSwitcher() {
  const { user, childId, pickChild } = useAuth();
  const [kids, setKids] = useState([]);
  useEffect(() => { api.get("/students", { params: { page_size: 20 } }).then((r) => { setKids(r.data.items); if (!r.data.items.find((k) => k.id === childId) && r.data.items[0]) pickChild(r.data.items[0].id); }); }, []); // eslint-disable-line
  if (user.role !== "parent" || kids.length < 1) return null;
  return <div className="w-44 hidden sm:block"><SelectField value={childId} onChange={pickChild} options={kids.map((k) => ({ value: k.id, label: k.name }))} testid="child-switcher" /></div>;
}

function Crumbs() {
  const { pathname } = useLocation();
  const parts = pathname.split("/").filter(Boolean).slice(1).filter((p) => p.length < 20);
  return (
    <div className="hidden lg:flex items-center gap-1 text-sm text-muted-foreground" data-testid="breadcrumbs">
      <Link to="/app" className="hover:text-foreground">Home</Link>
      {parts.map((p, i) => { const to = "/app/" + parts.slice(0, i + 1).join("/"); return (
        <span key={to} className="flex items-center gap-1"><ChevronRight className="h-3.5 w-3.5" />
          <Link to={to} className={i === parts.length - 1 ? "text-foreground font-medium" : "hover:text-foreground"}>{labelForPath(to) || titleCase(p.replace(/-/g, " "))}</Link></span>); })}
    </div>
  );
}

export default function AppLayout() {
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("sms_sidebar") === "1");
  const [mobile, setMobile] = useState(false);
  const [dark, setDark] = useTheme();
  const nav = useNavigate();
  useEffect(() => { localStorage.setItem("sms_sidebar", collapsed ? "1" : "0"); }, [collapsed]);
  const doLogout = async () => { await logout(); nav("/login"); };
  return (
    <div className="min-h-screen flex bg-background">
      <aside className={`hidden md:flex flex-col bg-[hsl(var(--sidebar))] sticky top-0 h-screen transition-[width] duration-300 ${collapsed ? "w-[76px]" : "w-[264px]"}`} data-testid="sidebar">
        <Brand collapsed={collapsed} />
        <SideNav collapsed={collapsed} />
        <button onClick={() => setCollapsed(!collapsed)} className="m-3 flex items-center justify-center gap-2 rounded-lg py-2 text-xs text-slate-400 hover:bg-white/5 hover:text-white" data-testid="sidebar-toggle-button">
          <ChevronsLeft className={`h-4 w-4 transition-transform ${collapsed ? "rotate-180" : ""}`} />{!collapsed && "Collapse"}
        </button>
      </aside>
      <Sheet open={mobile} onOpenChange={setMobile}>
        <SheetContent side="left" className="p-0 w-[270px] bg-[hsl(var(--sidebar))] border-0 flex flex-col"><Brand className="pr-12" /><SideNav onNavigate={() => setMobile(false)} /></SheetContent>
      </Sheet>
      <div className="flex-1 min-w-0 flex flex-col">
        <header className="sticky top-0 z-30 h-16 border-b bg-background/80 backdrop-blur-xl flex items-center gap-3 px-4 sm:px-6 no-print" data-testid="top-header">
          <Button variant="ghost" size="icon" className="md:hidden" onClick={() => setMobile(true)} aria-label="Open menu" data-testid="mobile-menu-btn"><Menu className="h-5 w-5" /></Button>
          <Crumbs />
          <div className="flex-1" />
          <SearchBox />
          <ChildSwitcher />
          <Button variant="ghost" size="icon" onClick={() => setDark(!dark)} aria-label="Toggle theme" data-testid="theme-toggle-button">{dark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}</Button>
          <Notifications />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex items-center gap-2 rounded-full pl-1 pr-3 py-1 hover:bg-muted transition-colors" data-testid="profile-menu-trigger">
                <div className="h-8 w-8 rounded-full bg-[#0A192F] dark:bg-sky-500 text-white grid place-items-center text-sm font-bold">{user.name?.[0]}</div>
                <span className="hidden sm:block text-left"><span className="block text-sm font-semibold leading-tight max-w-[140px] truncate">{user.name}</span><span className="block text-[11px] text-muted-foreground capitalize">{user.role}</span></span>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel><p className="truncate">{user.email}</p><div className="mt-1"><Badge value={user.role} /></div></DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => nav("/app/profile")} data-testid="menu-profile"><UserCircle className="h-4 w-4 mr-2" />My Profile</DropdownMenuItem>
              <DropdownMenuItem onClick={() => nav("/app/profile?tab=password")} data-testid="menu-change-password"><KeyRound className="h-4 w-4 mr-2" />Change Password</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={doLogout} className="text-rose-600" data-testid="logout-btn"><LogOut className="h-4 w-4 mr-2" />Log out</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </header>
        <main className="flex-1"><Outlet /></main>
      </div>
    </div>
  );
}
