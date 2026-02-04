import "./App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { useEffect, useState } from "react";

import { TemplateListPage } from "./pages/TemplateListPage";
import { TemplateEditorPage } from "./pages/TemplateEditorPage";
import { NewTemplatePage } from "./pages/NewTemplatePage";
import { SkillsListPage } from "./pages/SkillsListPage";
import { SkillCreatePage } from "./pages/SkillCreatePage";
import { TutorListPage } from "./pages/TutorListPage";
import { TutorHomePage } from "./pages/TutorHomePage";
import { TutorCreatePage } from "./pages/TutorCreatePage";
import { TutorSchedulePage } from "./pages/TutorSchedulePage";
import { StudentListPage } from "./pages/StudentListPage";
import { StudentHomePage } from "./pages/StudentHomePage";
import { StudentCreatePage } from "./pages/StudentCreatePage";
import SkillsPage from "./pages/SkillsPage";
import PrinciplesPage from "./pages/PrinciplesPage";
import FeedbackPage from "./pages/FeedbackPage";
import LoginPage from "./pages/LoginPage";

import "bootstrap/dist/css/bootstrap.min.css";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

// ------------------------------------------------------------
// PROTECTED ROUTE WRAPPER
// ------------------------------------------------------------

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem("access");

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

// function ProtectedRoute({ children }: ProtectedRouteProps) {
//   const [checking, setChecking] = useState(true);
//   const [valid, setValid] = useState(false);
//
//   useEffect(() => {
//     const token = localStorage.getItem("access");
//
//     if (!token) {
//       setChecking(false);
//       setValid(false);
//       return;
//     }
//
//     fetch("/api/auth/me/", {
//       headers: { Authorization: `Bearer ${token}` },
//     })
//       .then((res) => {
//         if (res.ok) {
//           setValid(true);
//         } else {
//           localStorage.removeItem("access");
//           localStorage.removeItem("refresh");
//           localStorage.removeItem("user");
//           setValid(false);
//         }
//       })
//       .catch(() => {
//         localStorage.removeItem("access");
//         localStorage.removeItem("refresh");
//         localStorage.removeItem("user");
//         setValid(false);
//       })
//       .finally(() => setChecking(false));
//   }, []);
//
//   if (checking) return <div className="p-4">Checking session…</div>;
//   if (!valid) return <Navigate to="/login" replace />;
//
//
//   return <>{children}</>;
// }


// ------------------------------------------------------------
// MAIN APP
// ------------------------------------------------------------
function App() {

  useEffect(() => {
    window.addEventListener("error", (e) => {
      console.log("GLOBAL ERROR:", e.error);
    });
  }, []);

  return (
    <BrowserRouter>
      <Routes>

        {/* PUBLIC ROUTES */}
        <Route path="/login" element={<LoginPage />} />

        {/* PROTECTED ROUTES */}
        <Route
          path="/templates"
          element={
            <ProtectedRoute>
              <TemplateListPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/templates/:id"
          element={
            <ProtectedRoute>
              <TemplateEditorPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/templates/new"
          element={
            <ProtectedRoute>
              <NewTemplatePage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/skills"
          element={
            <ProtectedRoute>
              <SkillsPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/skills/new"
          element={
            <ProtectedRoute>
              <SkillCreatePage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/skills/:id"
          element={
            <ProtectedRoute>
              <SkillsPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/skills/:parentId/new"
          element={
            <ProtectedRoute>
              <SkillCreatePage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/admin/tutors"
          element={
            <ProtectedRoute>
              <TutorListPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/admin/tutors/new"
          element={
            <ProtectedRoute>
              <TutorCreatePage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/tutor/:id"
          element={
            <ProtectedRoute>
              <TutorHomePage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/tutor/:id/schedule"
          element={
            <ProtectedRoute>
              <TutorSchedulePage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/admin/students"
          element={
            <ProtectedRoute>
              <StudentListPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/admin/students/new"
          element={
            <ProtectedRoute>
              <StudentCreatePage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/student/:id"
          element={
            <ProtectedRoute>
              <StudentHomePage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/principles"
          element={
            <ProtectedRoute>
              <PrinciplesPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/feedback"
          element={
            <ProtectedRoute>
              <FeedbackPage />
            </ProtectedRoute>
          }
        />

        {/* DEFAULT → PROTECTED HOME */}
        <Route
          path="*"
          element={
            <ProtectedRoute>
              <TemplateListPage />
            </ProtectedRoute>
          }
        />

      </Routes>
    </BrowserRouter>
  );
}

export default App;