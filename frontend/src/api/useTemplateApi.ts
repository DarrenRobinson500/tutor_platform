import { useState } from "react";
import { apiFetch, apiFetchJson } from "../utils/apiFetch"
import { TemplateSummary } from "../types/TemplateMetadata";

export function useTemplateApi() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function listTemplates(): Promise<TemplateSummary[]> {
    setLoading(true);
    setError(null);

    try {
      const res = await apiFetch("/api/templates/");
      if (!res.ok) throw new Error("Failed to load templates");
      return await res.json();
    } catch (err: any) {
      setError(err.message);
      return [];
    } finally {
      setLoading(false);
    }
  }

  async function getTemplate(id: string) {
    setLoading(true);
    setError(null);

    try {
      const res = await apiFetch(`/api/templates/${id}/`);
      if (!res.ok) throw new Error("Failed to load template");
      return await res.json();
    } catch (err: any) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  }


    async function saveTemplate(id: string | number, payload: any) {
      const isNew = id === "new";

      const url = isNew
        ? "/api/templates/"
        : `/api/templates/${id}/`;

      const method = isNew ? "POST" : "PUT";

      const res = await apiFetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      return res.ok ? await res.json() : null;
    }

    async function autosaveTemplate(id: number | string | null, content: string) {
      const res = await apiFetch("/api/templates/autosave/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, content }),
      });

      return res.ok ? await res.json() : { ok: false, status: res.status };

    }

    async function deleteTemplate(id: number) {
      await apiFetch(`/api/templates/${id}`, {
        method: "DELETE"
      });
    }

    function generateTemplate(skillId: number): Promise<TemplateSummary> {
        return apiFetchJson("/api/templates/generate/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ skill_id: skillId }),
        });

    }

    async function saveDiagram(id: number, svg: string) {
      return apiFetchJson(`/api/templates/${id}/diagram/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ svg })
      });
    }



    return {
      listTemplates,
      getTemplate,
      saveTemplate,
      autosaveTemplate,
      deleteTemplate,
      generateTemplate,
      loading,
      error,
    }
}