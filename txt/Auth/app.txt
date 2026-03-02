import "./App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useEffect } from "react";

import { TemplateListPage } from "./pages/TemplateListPage";
import { TemplateEditorPage } from "./pages/TemplateEditorPage";
import { NewTemplatePage } from "./pages/NewTemplatePage";
import { SkillCreatePage } from "./pages/SkillCreatePage";
import { TutorListPage } from "./pages/TutorListPage";
import { TutorHomePage } from "./pages/TutorHomePage";
import { TutorCreatePage } from "./pages/TutorCreatePage";
import { TutorSchedulePage } from "./pages/TutorSchedulePage";
import { TutorBookingPage } from "./pages/TutorBookingPage";
import { StudentListPage } from "./pages/StudentListPage";
import { StudentEditPage } from "./pages/StudentEditPage";
import { StudentQuestionPage } from "./pages/StudentQuestionPage";
import { StudentHomePage } from "./pages/StudentHomePage";
import { StudentBookingPage } from "./pages/StudentBookingPage";
import { StudentCreatePage } from "./pages/StudentCreatePage";
import SkillsPage from "./pages/SkillsPage";
import PrinciplesPage from "./pages/PrinciplesPage";
import FeedbackPage from "./pages/FeedbackPage";
import LoginPage from "./pages/LoginPage";

import "bootstrap/dist/css/bootstrap.min.css";


// ------------------------------------------------------------
// PROTECTED ROUTE WRAPPER
// ------------------------------------------------------------
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem("access");
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}


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

        {/* PUBLIC */}
        <Route path="/login" element={<LoginPage />} />

        {/* PROTECTED */}
        <Route path="/templates" element={<ProtectedRoute><TemplateListPage /></ProtectedRoute>} />
        <Route path="/templates/new" element={<ProtectedRoute><NewTemplatePage /></ProtectedRoute>} />
        <Route path="/templates/:id" element={<ProtectedRoute><TemplateEditorPage /></ProtectedRoute>} />

        <Route path="/skills" element={<ProtectedRoute><SkillsPage /></ProtectedRoute>} />
        <Route path="/skills/new" element={<ProtectedRoute><SkillCreatePage /></ProtectedRoute>} />
        <Route path="/skills/:id" element={<ProtectedRoute><SkillsPage /></ProtectedRoute>} />
        <Route path="/skills/:parentId/new" element={<ProtectedRoute><SkillCreatePage /></ProtectedRoute>} />
        <Route path="/admin/tutors" element={<ProtectedRoute><TutorListPage /></ProtectedRoute>} />
        <Route path="/admin/tutors/new" element={<ProtectedRoute><TutorCreatePage /></ProtectedRoute>} />
        <Route path="/tutor/:id" element={<ProtectedRoute><TutorHomePage /></ProtectedRoute>} />
        <Route path="/tutor/:id/schedule" element={<ProtectedRoute><TutorSchedulePage /></ProtectedRoute>} />
        <Route path="/tutor/:id/booking" element={<ProtectedRoute><TutorBookingPage /></ProtectedRoute>} />
        <Route path="/admin/students" element={<ProtectedRoute><StudentListPage /></ProtectedRoute>} />
        <Route path="/admin/students/new" element={<ProtectedRoute><StudentCreatePage /></ProtectedRoute>} />
        <Route path="/students/:studentId/edit" element={<ProtectedRoute><StudentEditPage /></ProtectedRoute>} />
        <Route path="/students/:studentId/test/:skillId" element={<ProtectedRoute><StudentQuestionPage /></ProtectedRoute>} />
        <Route path="/student/:id/booking" element={<ProtectedRoute><StudentBookingPage /></ProtectedRoute>} />
        <Route path="/student/:id" element={<ProtectedRoute><StudentHomePage /></ProtectedRoute>} />
        <Route path="/principles" element={<ProtectedRoute><PrinciplesPage /></ProtectedRoute>} />
        <Route path="/feedback" element={<ProtectedRoute><FeedbackPage /></ProtectedRoute>} />
        <Route path="*" element={<ProtectedRoute><TemplateListPage /></ProtectedRoute>} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;