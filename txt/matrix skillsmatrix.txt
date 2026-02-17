import React, { useEffect, useState } from "react";
import { apiFetch } from "../../utils/apiFetch";
import { useTemplateApi } from "../../api/useTemplateApi";
import { useNavigate } from "react-router-dom";

interface CellData {
  colour: string;
  count: number | null;
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

interface MatrixResponse {
  grades: (string | number)[];
  skills: SkillRow[];
}

// type Skill = {
//   id: number;
//   parent_id: number | null;
//   children_count: number;
//   depth: number;
//   description: string;
//   cells: Record<string, { colour: string; count: number }>;
// };

// type FlatRow = [Skill, number];

export function SkillsMatrix() {
  const [data, setData] = useState<MatrixResponse | null>(null);
  const [selectedGrade, setSelectedGrade] = useState<string | number | null>(null);
  const { generateTemplate, getFirstTemplate } = useTemplateApi();
  const navigate = useNavigate();
  const [loadingCell, setLoadingCell] = useState<{ skillId: number; grade: string | number } | null>(null);

  useEffect(() => {
    apiFetch(`/api/skills/matrix/?grade=All`)
      .then(res => res.json())
      .then(data => setData(data));
  }, []);

  useEffect(() => {
    const grade = selectedGrade ?? "All";

    apiFetch(`/api/skills/matrix/?grade=${grade}`)
      .then(res => res.json())
      .then(data => setData(data));
  }, [selectedGrade]);


  function handleCreateTemplate(skillId: number, grade: string | number) {
    setLoadingCell({ skillId, grade });

    generateTemplate(skillId, grade)
      .then((template) => {
        navigate(`/templates/${template.id}`);
      })
      .catch((err) => {
        console.error("Template generation failed:", err);
      })
      .finally(() => {
        setLoadingCell(null);
      });
  }

async function handleViewTemplate(skillId: number, grade: string | number) {
  try {
    const res = await apiFetch("/api/templates/preview/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        skill: skillId,
        grade: grade,
        difficulty: "easy"
      })
    });

    const data = await res.json();

    if (data.ok) {
      navigate(`/templates/${data.template_id}`);
    } else {
      alert(data.error || "No templates exist yet for this skill.");
    }
  } catch (err) {
    console.error("Failed to load first template:", err);
  }
}

  if (!data) {
    return (
      <div className="d-flex justify-content-center align-items-center" style={{ height: "200px" }}>
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Loading…</span>
        </div>
      </div>
    );
  }

  return (
    <div className="skills-matrix-container">

      {/* ⭐ Grade Filter Buttons */}
      <div className="mb-3 d-flex gap-2">
        {data.grades.map(g => (
          <button
            key={g}
            className={`btn ${selectedGrade === g ? "btn-primary" : "btn-outline-primary"}`}
            onClick={() => setSelectedGrade(g)}
          >
            {g}
          </button>
        ))}

        <button
          className={`btn ${selectedGrade === null ? "btn-secondary" : "btn-outline-secondary"}`}
          onClick={() => setSelectedGrade(null)}
        >
          All
        </button>
      </div>

      <table className="skills-matrix">
        <thead>
          <tr>
            <th className="skill-header">Skill</th>
            <th className="skill-header">Templates</th>
            <th className="skill-header">Actions</th>
          </tr>
        </thead>

        <tbody>
          {data.skills.map(skill => {

            const gradeStr = selectedGrade ? String(selectedGrade) : null;
            const cell = gradeStr ? skill.cells[gradeStr] : null;
            const isParent = skill.children_count > 0;
            const isLoading =
              loadingCell &&
              loadingCell.skillId === skill.id &&
              loadingCell.grade === selectedGrade;

            const templateCount = gradeStr && cell ? cell.count : null;

            return (
              <tr key={skill.id} className={isParent ? "parent-row" : ""}>

                <td style={{ paddingLeft: `${skill.depth * 20 + 10}px` }}>
                  {skill.description}
                </td>

                <td>
                  {templateCount !== null ? templateCount : "-"}
                </td>

                <td className="d-flex gap-2 align-items-center">

                  {selectedGrade && selectedGrade !== "All" && skill.children_count === 0 && (
                    <div className="d-flex gap-2 mt-1">

                      {/* Spinner OR Create button */}
                      {isLoading ? (
                        <div className="spinner-border spinner-border-sm text-success" role="status" />
                      ) : (
                        cell?.colour === "covered" && (
                          <button
                            className="btn btn-outline-primary btn-sm"
                            onClick={() => handleCreateTemplate(skill.id, selectedGrade)}
                          >
                            Create Templates
                          </button>
                        )
                      )}

                      {/* View button */}
                      {!isLoading && cell?.count! > 0 && (
                        <button
                          className="btn btn-outline-primary btn-sm"
                          onClick={() => handleViewTemplate(skill.id, selectedGrade)}
                        >
                          View Templates
                        </button>
                      )}

                    </div>
                  )}

                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}