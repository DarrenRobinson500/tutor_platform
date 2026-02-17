import type { TemplateMetadata } from "../../types/TemplateMetadata";

interface TemplateMetadataBarProps {
  metadata: TemplateMetadata;
  onChange: (updated: Partial<TemplateMetadata>) => void;
  onSave: () => void;
  isSaving: boolean;
  saveSuccess: boolean;
  saveError: string | null;
  onValidate: () => void;
  onPreview: () => void;
  onToSkill: () => void;
  onNext: () => void;
  onPrev: () => void;
  skills: Array<{ id: number; description: string }>;
  subjects: string[];
  onSubjectChange: (subject: string) => void;

}

export function TemplateMetadataBar({
  metadata,
  onChange,
  onSave,
  onValidate,
  onPreview,
  onToSkill,
  isSaving,
  saveError,
  saveSuccess,
  onNext,
  onPrev,
  skills,
  subjects,
  onSubjectChange,
}: TemplateMetadataBarProps) {

  if (!metadata) {
    return <div style={{ padding: 12 }}>Loading…</div>;
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 16, padding: 12 }}>

      {/* Grade */}
      Grade:
      <select
        className="form-select"
        style={{ width: "90px" }}
        value={metadata.grade ?? ""}
        onChange={(e) => onChange({ grade: e.target.value })}
      >
        <option value="">Select grade</option>
        {["K","1","2","3","4","5","6","7","8","9","10"].map(g => (
          <option key={g} value={g}>{g}</option>
        ))}
      </select>

      {/* Skill dropdown */}
      <select
        className="form-select"
        value={metadata.skill ?? ""}
        onChange={(e) => onChange({ skill: Number(e.target.value) })}
      >
        <option value="">Select skill</option>
        {skills.map((s) => (
          <option key={s.id} value={s.id}>
            {s.description}
          </option>
        ))}
      </select>

      {/* Difficulty */}
      <select
        className="form-select"
        style={{ width: "90px" }}
        value={metadata.difficulty ?? ""}
        onChange={(e) => onChange({ difficulty: e.target.value })}
      >
        <option value="">Difficulty</option>
        <option value="easy">Easy</option>
        <option value="medium">Medium</option>
        <option value="hard">Hard</option>
      </select>

      {/* Subject dropdown */}
      <select
        className="form-select"
        style={{ width: "400px" }}   // adjust as needed
        value={metadata.subject ?? ""}
        onChange={(e) => onSubjectChange(e.target.value)}
      >
        <option value="">All subjects</option>
        {subjects.map((subj) => (
          <option key={subj} value={subj}>
            {subj}
          </option>
        ))}
      </select>

      <button className="btn btn-secondary" onClick={onPrev}>Previous</button>
      <button className="btn btn-secondary" onClick={onNext}>Next</button>

      {/* Save button */}
      <button
        type="button"
        className="btn btn-primary"
        onClick={onSave}
        disabled={isSaving}
      >
        {isSaving ? "Saving..." : "Save"}
      </button>

      {saveSuccess && <span style={{ color: "green" }}>Saved successfully</span>}
      {saveError && <span style={{ color: "red" }}>{saveError}</span>}

      <button onClick={onValidate} className="btn btn-primary">Validate</button>
      <button onClick={onPreview} className="btn btn-primary">Preview</button>
    </div>
  );
}