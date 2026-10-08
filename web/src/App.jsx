import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Layout from "./components/Layout";
import Assistant from "./pages/Assistant";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";

export const DASH_ROLES = ["technician", "manager", "admin"];

export default function App() {
  const { user, ready } = useAuth();
  if (!ready) return <div className="splash" />;
  if (!user) {
    return (
      <Routes>
        <Route path="*" element={<Login />} />
      </Routes>
    );
  }
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Assistant />} />
        <Route path="c/:id" element={<Assistant />} />
        {DASH_ROLES.includes(user.role) && <Route path="dashboard" element={<Dashboard />} />}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}