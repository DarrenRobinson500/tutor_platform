import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Breadcrumbs } from "./components/Breadcrumbs";
import { SkillsMatrix } from "./components/SkillsMatrix";
import { Layout } from "./components/Layout";
import { apiFetch } from "../utils/apiFetch";

export default function SkillsPage() {
  const { id } = useParams();
  const [skill, setSkill] = useState<any>(null);
  const [parents, setParents] = useState<any[]>([]);
  const [templates, setTemplates] = useState<any[]>([]);

  // Load skill + parents
  useEffect(() => {
    if (!id) {
      setSkill(null);
      setParents([]);
      return;
    }

    const skillId = Number(id);

    apiFetch(`/api/skills/${skillId}/`)
      .then(res => res.json())
      .then(data => setSkill(data));

    apiFetch(`/api/skills/${skillId}/parents/`)
      .then(res => res.json())
      .then(data => setParents(data));
  }, [id]);

  // Load direct templates
  useEffect(() => {
    if (!id) {
      setTemplates([]);
      return;
    }

    apiFetch(`/api/skills/${id}/direct_templates/`)
      .then(res => res.json())
      .then(data => setTemplates(data));
  }, [id]);

  if (id && !skill) {
    return <Layout><div className="container mt-4">Loading...</div></Layout>;
  }

  return (
    <Layout>
      <div className="container mt-4">

        {skill && (
          <>
            <Breadcrumbs parents={parents} current={skill} />

            <h1 className="skill-heading">{skill.description}</h1>
            <div className="skill-meta">
              <span>Grade: {skill.grade_level}</span>
            </div>

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

        <h1>Skills</h1>
        <SkillsMatrix />
      </div>
    </Layout>
  );
}