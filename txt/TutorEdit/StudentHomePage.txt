import { useParams, useNavigate } from "react-router-dom";
import React, { useState, useEffect } from "react";
// import { WeeklyCalendar } from "./components/WeeklyCalendar";
import { Layout } from "./components/Layout";
// import { WeekData } from "../types/weekly";
import { apiFetch } from "../utils/apiFetch";

interface CellData {
  colour: string;
  count: number | null;
  validated: number;
  unvalidated: number;
}

interface SkillRow {
  id: number;
  code: string;
  description: string;
  depth: number;
  parent_id: number | null;
  children_count: number;
  cells: Record<string, CellData>;
}

export function StudentHomePage() {
  const { id } = useParams();
  const [student, setStudent] = useState<any>(null);
//   const [tutorSettings, setTutorSettings] = useState<any>(null);
  const navigate = useNavigate();
//   const { studentId } = useParams();
  const [syllabus, setSyllabus] = useState<SkillRow[]>([]);
  const [mastery, setMastery] = useState<any>({});


  useEffect(() => {
    apiFetch(`/api/students/${id}/home/`)
      .then((res) => res.json())
      .then(async (data) => {
        setStudent(data);

      });
  }, [id]);

//   const tutorId = student?.tutor_id;

  useEffect(() => {
    if (!student?.year_level) return;

    apiFetch(`/api/skills/matrix/?grade=${student.year_level}&student_id=${id}`)
      .then(res => res.json())
      .then(data => {
        setSyllabus(data.skills);
        setMastery(data.mastery);
      });
  }, [student]);

  if (!student) {
    return (
      <Layout>
        <div className="container mt-4">Loading…</div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="container mt-4">
        <h1>Welcome back {student.name}</h1>
        <p><strong>Email:</strong> {student.email}<br/>
        <strong>Year Level:</strong> {student.year_level || "Not set"}<br/>
        <strong>Area of Study:</strong> {student.area_of_study || "Not set"}
        </p>
        <button
          className="btn btn-outline-primary"
          onClick={() => navigate(`/students/${id}/edit?returnTo=/students/${id}`)}
        >
          Edit My Details
        </button>



        <hr />
        <h3 className="mt-4">Your Syllabus</h3>

        {syllabus.length === 0 && (
          <p>No syllabus available for this year level.</p>
        )}

      <table className="skills-matrix">
        <thead>
          <tr>
            <th className="skill-header">Skill</th>
            <th className="skill-header">Skill Level</th>
            <th className="skill-header">Actions</th>
          </tr>
        </thead>

        <tbody>
          {syllabus.map(skill => {
            const isParent = skill.children_count > 0;
            const gradeStr = student.year_level ? String(student.year_level) : null;
            const cell = gradeStr ? skill.cells[gradeStr] : null;
            const templateCount = gradeStr && cell ? cell.validated : null;



            return (
              <tr key={skill.id} className={isParent ? "parent-row" : ""}>

                <td style={{ paddingLeft: `${skill.depth * 20 + 10}px` }}>
                  {skill.description}
                </td>

                <td>
                  {mastery[skill.id]?.competence_label ?? "—"}
                </td>

                <td>
                  {templateCount !== null && templateCount > 0 && (
                    <button
                      className="btn btn-sm btn-outline-primary"
                      onClick={() =>
                        navigate(`/students/${id}/test/${skill.id}`)
                      }
                    >
                      Practice
                    </button>
                  )}
                </td>


              </tr>
            );
          })}
        </tbody>
      </table>




      </div>
    </Layout>
  );
}