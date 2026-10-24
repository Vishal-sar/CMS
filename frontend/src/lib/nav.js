import { LayoutDashboard, UserPlus, GraduationCap, Users, UsersRound, School, BookOpen, CalendarCheck, CalendarClock, FileText, Award, Wallet,
  NotebookPen, Library, Bus, CalendarDays, Plane, Megaphone, BarChart3, ShieldCheck, ScrollText, Settings } from "lucide-react";

const A = ["admin"], AT = ["admin", "teacher"], ALL = ["admin", "teacher", "student", "parent"], FAM = ["student", "parent"];

export const NAV = [
  { group: "Main", items: [
    { to: "/app", label: "Overview", icon: LayoutDashboard, roles: ALL, end: true },
    { to: "/app/admissions", label: "Admissions", icon: UserPlus, roles: A },
    { to: "/app/students", label: "Students", icon: GraduationCap, roles: AT, labelFor: { teacher: "My Students" } },
    { to: "/app/teachers", label: "Teachers & Staff", icon: Users, roles: A },
    { to: "/app/parents", label: "Parents", icon: UsersRound, roles: A },
  ]},
  { group: "Academics", items: [
    { to: "/app/classes", label: "Classes & Sections", icon: School, roles: A },
    { to: "/app/subjects", label: "Subjects", icon: BookOpen, roles: A, labelFor: { teacher: "My Subjects" } },
    { to: "/app/attendance", label: "Attendance", icon: CalendarCheck, roles: ALL },
    { to: "/app/timetable", label: "Timetable", icon: CalendarClock, roles: ALL },
    { to: "/app/exams", label: "Examinations", icon: FileText, roles: AT },
    { to: "/app/results", label: "Marks & Results", icon: Award, roles: ALL },
    { to: "/app/homework", label: "Homework & Assignments", icon: NotebookPen, roles: ALL },
  ]},
  { group: "Operations", items: [
    { to: "/app/fees", label: "Fees & Payments", icon: Wallet, roles: ["admin", "student", "parent"] },
    { to: "/app/library", label: "Library", icon: Library, roles: ALL },
    { to: "/app/transport", label: "Transport", icon: Bus, roles: AT },
    { to: "/app/calendar", label: "Calendar & Events", icon: CalendarDays, roles: ALL },
    { to: "/app/leave", label: "Leave Management", icon: Plane, roles: ["admin", "teacher", "parent"] },
    { to: "/app/announcements", label: "Announcements", icon: Megaphone, roles: ALL },
  ]},
  { group: "Administration", items: [
    { to: "/app/reports", label: "Reports & Analytics", icon: BarChart3, roles: A },
    { to: "/app/users", label: "User Management", icon: ShieldCheck, roles: A },
    { to: "/app/audit", label: "Audit Logs", icon: ScrollText, roles: A },
    { to: "/app/settings", label: "Settings", icon: Settings, roles: A },
  ]},
];

export const navFor = (role) => NAV.map((g) => ({ ...g, items: g.items.filter((i) => i.roles.includes(role)).map((i) => ({ ...i, label: i.labelFor?.[role] || i.label })) })).filter((g) => g.items.length);
export const labelForPath = (path) => NAV.flatMap((g) => g.items).find((i) => i.to === path)?.label;
export { FAM };
