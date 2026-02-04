import yaml from "js-yaml";
import debounce from "lodash.debounce";

import { useEffect, useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { TemplateMetadataBar } from "./components/TemplateMetadataBar";
import { EditorPanel } from "./components/EditorPanel";
import { ValuesPanel } from "./components/ValuesPanel";
import { PreviewPanel } from "./components/PreviewPanel";
import { LogsPanel } from "./components/LogsPanel";
import { Layout } from "./components/Layout";
import { DiagramEditor } from "./components/DiagramEditor";
import { renderDiagramFromCode } from "../diagram/engine";
import { apiFetch, apiFetchJson } from "../utils/apiFetch"

// API hooks
import { useTemplateApi } from "../api/useTemplateApi";
import { useValidationApi } from "../api/useValidationApi";
import { usePreviewApi } from "../api/usePreviewApi";
import type { TemplateMetadata } from "../types/TemplateMetadata";

interface PreviewResponse {
  question: string;
  answers: any[];
  params: Record<string, any>;
  solution: string;
  diagram_svg: string;
  diagram_code: string;
  substituted_yaml: string;
}


export function TemplateEditorPage() {
  const emptyMetadata = {
    id: null,
    name: "",
    description: "",
    subject: "",
    topic: "",
    subtopic: "",
    difficulty: "",
    tags: [],
    curriculum: [],
    status: "draft",
    version: 1,
    skill: null,
  };

  const navigate = useNavigate();
  const params = useParams();
  const { id } = params;
  const [metadata, setMetadata] = useState<TemplateMetadata>(emptyMetadata);
  const isNew = id === "new";
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [content, setContent] = useState<string>("");
  const [validationResult, setValidationResult] = useState<any>(null);
  const [previewResult, setPreviewResult] = useState<any>(null);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const { getTemplate, saveTemplate } = useTemplateApi();
  const { validateTemplate } = useValidationApi();
  const { previewTemplate } = usePreviewApi();

  function buildMetadataFromTemplate(tpl: any): TemplateMetadata {
    return {
      id: tpl.id ?? null,
      name: tpl.name ?? "",
      description: tpl.description ?? "",
      subject: tpl.subject ?? "",
      topic: tpl.topic ?? "",
      subtopic: tpl.subtopic ?? "",
      difficulty: tpl.difficulty ?? "",
      tags: tpl.tags ?? [],
      curriculum: tpl.curriculum ?? [],
      status: tpl.status ?? "draft",
      version: tpl.version ?? 1,
      skill: tpl.skill ?? null,
    };
  }



  // Debounced function
  const debouncedPreview = useRef(
    debounce(async (content: string) => {
      const res = await apiFetch("/api/templates/preview/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });

      const data = await res.json();
      console.log("Preview response:", data.preview);
      console.log("Sending content to preview:", content);

      setPreview(data.preview);
    }, 400)
  ).current;

  function extractDiagramSvg(yamlText: string): string {
    try {
      const parsed: any = yaml.load(yamlText);
      return parsed?.diagram?.svg || "";
    } catch {
      return "";
    }
  }

// function updateYamlWithDiagram(originalYaml: string, newSvg: string, newCode: string): string {
//   let parsed: any;
//
//   try {
//     parsed = yaml.load(originalYaml) || {};
//   } catch {
//     return originalYaml;
//   }
//
//   if (!parsed.diagram) {
//     parsed.diagram = {};
//   }
//
//   parsed.diagram.type = "svg";
//   parsed.diagram.code = newCode;
//   parsed.diagram.svg = newSvg;
//
//   return yaml.dump(parsed, { lineWidth: -1 });
// }


  useEffect(() => {
    async function load() {
      if (!id) return;

      const tpl = await getTemplate(id);
      if (!tpl) return;

      // 1. Load YAML into the editor
      setContent(tpl.content);

      // 2. Load metadata
      setMetadata(buildMetadataFromTemplate(tpl));

      // 3. Generate initial preview
      const res = await apiFetch("/api/templates/preview/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: tpl.content }),
      });
      const data = await res.json();
      setPreview(data.preview);
      console.log("FRONTEND RECEIVED PREVIEW:", data);
    }
    load();
  }, [id]);

  // Handler - Change
  function handleContentChange(newContent: string) {
    setContent(newContent);
    debouncedPreview(newContent);
  }

  const handleToSkill = () => {
    if (metadata.skill) {
      navigate(`/skills/${metadata.skill}`);
    }
  };

//   const handleEditorChange = (newValue: string) => {
//     setContent(newValue);
//     if (!newValue.trim()) {
//       setValidationResult(null);
//       setPreviewResult(null);
//       return; // stop here — do NOT call backend
//     }
//   };

  // Handler - Save
const handleSave = async () => {
  console.log("Save button clicked (TemplateEditorPage) — metadata:", metadata);

  // Build a clean payload that matches the Django Template model
  const payload = {
    name: metadata.name || "",
    description: metadata.description || "",
    subject: metadata.subject || "",
    topic: metadata.topic || "",
    subtopic: metadata.subtopic || "",
    difficulty: metadata.difficulty || "",
    tags: metadata.tags || [],
    curriculum: metadata.curriculum || [],
    skill: metadata.skill || null,
    content
  };

  // CREATE
  if (!metadata.id) {
    console.log("Creating new template with payload:", payload);

    const res = await apiFetch("/api/templates/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const errorText = await res.text();
      console.error("Template CREATE failed:", errorText);
      alert("Template creation failed. Check console for details.");
      return;
    }

    const data = await res.json();
    console.log("Template created:", data);

    // Store the new ID
    setMetadata(prev => ({ ...prev, id: data.id }));

    // Navigate to the new template page
    navigate(`/templates/${data.id}`);
    return;
  }

  // UPDATE
  console.log("Updating existing template:", metadata.id);

  const res = await apiFetch(`/api/templates/${metadata.id}/`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorText = await res.text();
    console.error("Template UPDATE failed:", errorText);
    alert("Template update failed. Check console for details.");
    return;
  }

  const data = await res.json();
  console.log("Template updated:", data);

  // Update metadata (in case backend modifies anything)
  setMetadata(prev => ({ ...prev, ...data }));
};

  const handleValidate = async () => {
    const result = await validateTemplate({ content });
    setValidationResult(result);
  };

  const handlePreview = async () => {
    setPreviewResult({
      text: "This is a preview of your template.\n\nMore features coming soon."
    });
  };

  const handleMetadataChange = (updated: Partial<TemplateMetadata>) => {
      setMetadata(prev => ({
        ...prev,
        ...updated
      }));
    };

  return (
<Layout>
  <div className="template-editor-page">

    {/* Top metadata + actions */}
    <TemplateMetadataBar
      metadata={metadata}
      onChange={handleMetadataChange}
      onSave={handleSave}
      onValidate={handleValidate}
      onPreview={handlePreview}
      isSaving={isSaving}
      saveError={saveError}
      saveSuccess={saveSuccess}
      onToSkill={handleToSkill}
    />

    <div className="container-fluid">
      <div className="row" style={{ height: "70vh" }}>

        {/* Panel 1: Editor (Template source) */}
        <div className="col-md-4 d-flex flex-column" style={{ height: "100%" }}>
          <div className="card shadow-sm flex-grow-1">
            <div className="card-header">Question Definition</div>
            <div
              className="card-body p-0 d-flex flex-column"
              style={{ overflow: "hidden" }}
            >
              <EditorPanel
                content={content}
                onChange={handleContentChange}
                validation={validationResult}
                templateId={id ?? null}
              />
            </div>
          </div>
        </div>

        {/* Panel 2: Values (Substituted YAML) */}
        <div className="col-md-4 d-flex flex-column" style={{ height: "100%" }}>
          <div className="card shadow-sm flex-grow-1">
            <div className="card-header">Question Definition (Values Populated)</div>
            <div className="card-body overflow-auto">
              <ValuesPanel substitutedYaml={preview?.substituted_yaml ?? null} />
            </div>
          </div>
        </div>

        {/* Panel 3: Preview (Student view + Diagram) */}
        <div className="col-md-4 d-flex flex-column" style={{ height: "100%" }}>
          <div className="card shadow-sm flex-grow-1">
            <div className="card-header">Student Preview</div>
            <div
              className="card-body p-2 d-flex flex-column"
              style={{ overflow: "hidden" }}
            >
              <PreviewPanel
                preview={preview}
                templateContent={content}
                onNext={(newPreview) => setPreview(newPreview)}
              />
            </div>
          </div>
        </div>

      </div>
    </div>

  </div>
</Layout>
  );
}