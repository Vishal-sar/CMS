import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, Protected } from "@/lib/auth";
import AppLayout from "@/components/app/Layout";
import Landing from "@/pages/Landing";
import { Login, ForgotPassword, ResetPassword } from "@/pages/Auth";
import Dashboard from "@/pages/Dashboard";
import Students, { StudentProfile } from "@/pages/Students";
import { Teachers, Parents, Users, Classes } from "@/pages/People";
import { Subjects, Timetable } from "@/pages/Academic";
import Attendance from "@/pages/Attendance";
import Exams, { Results, ReportCard } from "@/pages/Exams";
import Fees, { PaymentResult } from "@/pages/Fees";
import Homework from "@/pages/Homework";
import { Library, Transport } from "@/pages/Ops";
import { CalendarPage, Leave, Announcements } from "@/pages/Comms";
import { Reports, Audit, Settings, Profile } from "@/pages/Admin";

const A = ["admin"], AT = ["admin", "teacher"];
const R = (roles, el) => <Protected roles={roles}>{el}</Protected>;

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/payment-result" element={<Navigate to={`/app/payment-result${window.location.search}`} replace />} />
          <Route path="/app" element={<Protected><AppLayout /></Protected>}>
            <Route index element={<Dashboard />} />
            <Route path="admissions" element={R(A, <Students admissions />)} />
            <Route path="students" element={R(AT, <Students />)} />
            <Route path="students/:id" element={<StudentProfile />} />
            <Route path="teachers" element={R(A, <Teachers />)} />
            <Route path="parents" element={R(A, <Parents />)} />
            <Route path="classes" element={R(A, <Classes />)} />
            <Route path="subjects" element={R(AT, <Subjects />)} />
            <Route path="attendance" element={<Attendance />} />
            <Route path="timetable" element={<Timetable />} />
            <Route path="exams" element={R(AT, <Exams />)} />
            <Route path="results" element={<Results />} />
            <Route path="report-card/:eid/:sid" element={<ReportCard />} />
            <Route path="fees" element={R(["admin", "student", "parent"], <Fees />)} />
            <Route path="payment-result" element={<PaymentResult />} />
            <Route path="homework" element={<Homework />} />
            <Route path="library" element={<Library />} />
            <Route path="transport" element={R(AT, <Transport />)} />
            <Route path="calendar" element={<CalendarPage />} />
            <Route path="leave" element={R(["admin", "teacher", "parent"], <Leave />)} />
            <Route path="announcements" element={<Announcements />} />
            <Route path="reports" element={R(A, <Reports />)} />
            <Route path="users" element={R(A, <Users />)} />
            <Route path="audit" element={R(A, <Audit />)} />
            <Route path="settings" element={R(A, <Settings />)} />
            <Route path="profile" element={<Profile />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster richColors position="top-right" />
    </AuthProvider>
  );
}
