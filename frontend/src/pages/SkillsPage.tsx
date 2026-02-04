import React from "react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Link } from "react-router-dom";

import { SkillsListPage } from "./SkillsListPage";
import { SkillDetail } from "./components/SkillDetail";
import { useNavigate } from "react-router-dom";
import { Breadcrumbs } from "./components/Breadcrumbs";
import { useSkillsApi, Skill } from "../api/useSkillsApi";
import { Layout } from "./components/Layout";
import { useTemplateApi } from "../api/useTemplateApi";
import { TemplateSummary } from "../types/TemplateMetadata";
import { apiFetch, apiFetchJson } from "../utils/apiFetch"

export default function SkillsPage() {
  const { getSkill, getParents, listSkills, deleteSkill, loading, error } = useSkillsApi();
  const [parents, setParents] = useState<Skill[]>([]);
  const [templates, setTemplates] = useState<any[]>([]);
  const { generateTemplate } = useTemplateApi();


  const { id } = useParams();
  const navigate = useNavigate();
  const [skill, setSkill] = useState<Skill | null>(null);
  const skillId = Number(id);

  const handleSelect = (skillId: number) => {
    navigate(`/skills/${skillId}`);
  };

useEffect(() => {
  if (!id) {
    // No skill selected → show top-level skills
    setSkill(null);
    setParents([]);
    return;
  }
  const skillId = Number(id);
  getSkill(skillId).then((s) => setSkill(s));
  getParents(skillId).then((p) => setParents(p));
}, [id]);

useEffect(() => {
  if (!id) {
    setTemplates([]);
    return;
  }
  apiFetch(`/api/skills/${id}/direct_templates/`)
    .then(res => res.json())
    .then(data => setTemplates(data));
}, [id]);

function handleCreateTemplate() {
  generateTemplate(Number(skillId))
    .then((template) => {
      console.log("Generated template:", template);
      navigate(`/templates/${template.id}`);
    })
    .catch((err) => {
      console.error("Template generation failed:", err);
    });
}


    if (id && !skill) {
      return <div>Loading...</div>;
    }

    return (
      <Layout>
        <div className="container mt-4">

          {/* If a skill is selected, show its details */}
          {skill && (
            <>
              <Breadcrumbs parents={parents} current={skill} />

              <h1 className="skill-heading">{skill.description}</h1>

              <div className="skill-meta">
                <span>Grade: {skill.grade_level}</span>
              </div>

                {skill.children_count === 0 && (
                  <button className="btn btn-success" onClick={handleCreateTemplate}>
                    Create Templates (this will take a minute or two)
                  </button>
                )}

              {templates.length > 0 && (
                <>
                  <h2>Templates for this Skill</h2>
                  <ul className="template-list">
                    {templates.map(t => (
                        <li key={t.id} className="template-item">
                          <Link to={`/templates/${t.id}`}>
                            {t.subject}
                          </Link>
                        </li>

                    ))}
                  </ul>
                </>
              )}
            </>
          )}


          <SkillsListPage
            parentId={id ? Number(id) : undefined}
            onSelect={(skillId) => navigate(`/skills/${skillId}`)}
          />

        </div>
      </Layout>
    );

}
