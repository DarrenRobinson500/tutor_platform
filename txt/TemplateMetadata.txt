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
  saveSuccess
}: TemplateMetadataBarProps) {

  if (!metadata) {
    return <div style={{ padding: 12 }}>Loading…</div>;
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 16,
        padding: 12,
        borderBottom: "1px solid #ddd",
        background: "#fafafa",
      }}
    >
<input
  className="form-control"
  value={metadata.name}
onChange={(e) =>
  onChange({
    name: e.target.value
  })
}

  style={{ fontSize: 18 }}
/>


      {/* Save button */}
      <button
        type="button"
        className="btn btn-primary"
        onClick={() => {
          console.log("Save button clicked (TemplateMetadataBar)");
          onSave();
        }}
        disabled={isSaving}
      >
        {isSaving ? "Saving..." : "Save"}
      </button>

      {/* Save status */}
      {saveSuccess && (
        <span style={{ color: "green" }}>
          Saved successfully
        </span>
      )}

      {saveError && (
        <span style={{ color: "red" }}>
          {saveError}
        </span>
      )}

      {/* Other actions */}
      {saveSuccess && (
        <span style={{ color: "green" }}>
          Saved successfully
        </span>
      )}

      {saveError && (
        <span style={{ color: "red" }}>
          {saveError}
        </span>
      )}

        <button
          type="button"
          className="btn btn-secondary"
          onClick={onToSkill}
        >
          Skill
        </button>


      <button onClick={onValidate} className="btn btn-primary">Validate</button>
      <button onClick={onPreview} className="btn btn-primary">Preview</button>
    </div>
  );
}