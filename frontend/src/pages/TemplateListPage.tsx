import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Layout } from "./components/Layout";
import { useTemplateApi } from "../api/useTemplateApi";
import type { TemplateSummary } from "../types/TemplateMetadata";


export function TemplateListPage() {
  const navigate = useNavigate();
  const { listTemplates, deleteTemplate, loading, error } = useTemplateApi();

  const [templates, setTemplates] = useState<TemplateSummary[]>([]);

  useEffect(() => {
    async function load() {
      const data = await listTemplates();
      setTemplates(data);
    }
    load();
  }, []);

  async function handleDelete(e: React.MouseEvent, id: number) {
    e.stopPropagation(); // prevent row click navigation

    if (!window.confirm("Delete this template?")) return;

    await deleteTemplate(id);
    setTemplates((prev) => prev.filter((t) => t.id !== id));
  }

  return (
    <Layout>
    <div>
      <div className="container mt-4">
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h1 className="h3">Templates</h1>

          <button
            className="btn btn-primary"
            onClick={() => navigate("/templates/new")}
          >
            Create New Template
          </button>
        </div>

        {loading && <p>Loading templates…</p>}
        {error && <p className="text-danger">{error}</p>}

        {!loading && templates.length === 0 && (
          <p>No templates found.</p>
        )}

        {templates.length > 0 && (
          <table className="table table-hover">
            <thead className="table-light">
              <tr>
                <th>Name</th>
                <th>Description</th>
                <th>Subject</th>
                <th>Status</th>
                <th>Updated</th>
                <th style={{ width: 80 }}></th>
              </tr>
            </thead>

            <tbody>
              {templates.map((tpl) => (
                <tr
                  key={tpl.id}
                  onClick={() => navigate(`/templates/${tpl.id}`)}
                  style={{ cursor: "pointer" }}
                >
                  <td>{tpl.name}</td>
                  <td>{tpl.description}</td>
                  <td>{tpl.subject}</td>
                  <td>{tpl.status}</td>
                  <td>{new Date(tpl.updated_at).toLocaleString()}</td>

                  <td>
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={(e) => handleDelete(e, tpl.id)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>


</Layout>

  );
}
