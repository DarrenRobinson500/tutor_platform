import { useState, useEffect } from "react";
import { Latex } from "./Latex";
import "katex/dist/katex.min.css";
import { apiFetch } from "../../utils/apiFetch";
import type { PreviewResponse, StudentRecordResponse } from "../../types/PreviewResponse";


interface PreviewPanelBase {
  preview: PreviewResponse | null;
}

/**
 * EDITOR MODE
 * - No student fields allowed
 * - templateContent + onEditorNext required
 */
interface PreviewPanelEditorProps extends PreviewPanelBase {
  mode: "editor";
  templateContent: string;
  onEditorNext: (newPreview: PreviewResponse) => void;

  // explicitly forbidden in editor mode
  templateId?: never;
  studentId?: never;
  onStudentNext?: never;
}

/**
 * STUDENT MODE
 * - templateId + studentId required
 * - onStudentNext required
 * - templateContent/onEditorNext forbidden
 */
interface PreviewPanelStudentProps extends PreviewPanelBase {
  mode: "student";
  templateId: number;
  studentId: number;
  onStudentNext: (result: StudentRecordResponse) => void;

  // explicitly forbidden in student mode
  templateContent?: never;
  onEditorNext?: never;
}

/**
 * UNION OF BOTH MODES
 */
export type PreviewPanelProps =
  | PreviewPanelEditorProps
  | PreviewPanelStudentProps;

export function PreviewPanel({
  preview,
  mode,
  templateContent,
  onEditorNext,
  templateId,
  onStudentNext,
  studentId,
}: PreviewPanelProps) {
  const [selected, setSelected] = useState<number | null>(null);
  const [isCorrect, setIsCorrect] = useState<boolean | null>(null);
  const [flagged, setFlagged] = useState(false);
  const [startTime, setStartTime] = useState<number>(Date.now());
  const [selectedAnswer, setSelectedAnswer] = useState<any>(null);
  const [showIncorrectFeedback, setShowIncorrectFeedback] = useState(false);
  const [backendResult, setBackendResult] = useState<any>(null);
  const [localTemplateId, setLocalTemplateId] = useState<number | null>(null);

  useEffect(() => {
    if (mode === "student" && templateId !== undefined) {
      console.log("Setting localTemplateId to:", templateId);
      setLocalTemplateId(templateId);
    }
  }, [templateId, mode]);

  useEffect(() => {
    setStartTime(Date.now());
    setSelected(null);
    setIsCorrect(null);
    setFlagged(false);
    setShowIncorrectFeedback(false);
    setSelectedAnswer(null);
    setBackendResult(null);
  }, [preview]);

  const safeLatex = (value: any): string => {
    if (value === null || value === undefined) return "";
    if (typeof value === "string" || typeof value === "number") return String(value);
    try {
      return JSON.stringify(value);
    } catch {
      return "";
    }
  };

  async function recordAttempt(answer: any, correct: boolean) {
    if (!preview) return null;

    const timeTaken = Date.now() - startTime;

    const res = await apiFetch("/api/questions/record/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        student_id: studentId,
        template_id: localTemplateId,
        params: preview.params,
        question_text: preview.question,
        correct_answer: preview.solution,
        selected_answer: answer?.text ?? null,
        correct,
        time_taken_ms: timeTaken,
        help_requested: flagged,
      }),
    });
    return res.json();
  }

  async function loadNextEditorPreview() {
    if (!templateContent) return;
    const res = await apiFetch("/api/templates/preview/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: templateContent }),
    });
    const data = await res.json();
    if (data.ok && data.preview) {
      onEditorNext?.(data.preview);
    }
  }

  async function loadNextStudentPreview() {
    if (!templateId) return;
    const res = await apiFetch("/api/templates/preview/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ templateId }),
    });
    const data = await res.json();
    if (data.ok && data.preview) {
      onStudentNext?.(data.preview);
    }
  }

  async function handleIDontGetIt() {
    setFlagged(true);

    if (mode === "student") {
      const result = await recordAttempt(selectedAnswer, false);
      setShowIncorrectFeedback(true);
      setBackendResult(result);
    }
  }

  async function handleAnswerClick(index: number, answer: any) {
    setSelected(index);
    setSelectedAnswer(answer);

    const correct = Boolean(answer.correct);
    setIsCorrect(correct);

    if (mode === "student") {
      const result = await recordAttempt(answer, correct);

      if (correct) {
        onStudentNext?.(result);
      } else {
        setShowIncorrectFeedback(true);
        setBackendResult(result);
      }
    }

    if (mode === "editor" && correct) {
      await loadNextEditorPreview();
    }
  }

  if (!preview) {
    return (
      <div style={{ padding: 12, color: "#888" }}>
        Start typing or load a question to see a preview…
      </div>
    );
  }

  if (Array.isArray(preview.errors) && preview.errors.length > 0) {
    return (
      <div style={{ padding: 12 }}>
        <div style={{ color: "red", marginBottom: 12 }}>
          Backend reported errors:
          <ul>
            {preview.errors.map((e: string, i: number) => (
              <li key={i}>{safeLatex(e)}</li>
            ))}
          </ul>
        </div>

        {preview.question && (
          <div style={{ marginBottom: 12, fontWeight: "bold" }}>
            <Latex>{safeLatex(preview.question)}</Latex>
          </div>
        )}

        {preview.diagram_svg && (
          <div
            dangerouslySetInnerHTML={{ __html: preview.diagram_svg }}
            style={{ marginBottom: 12 }}
          />
        )}
      </div>
    );
  }

  const question = safeLatex(preview.question);
  const solution = safeLatex(preview.solution);
  const answers = Array.isArray(preview.answers) ? preview.answers : [];
  const diagramSvg = preview.diagram_svg;

  return (
    <div style={{ padding: 12, fontSize: 18 }}>
      <div style={{ marginBottom: 12, fontWeight: "bold" }}>
        <Latex>{question}</Latex>
      </div>

      {diagramSvg && (
        <div style={{ display: "flex", justifyContent: "center", width: "100%" }}>
          <div dangerouslySetInnerHTML={{ __html: diagramSvg }} />
        </div>
      )}

      {answers.length > 0 && (
        <div className="d-flex flex-row flex-wrap gap-2">
          {answers.map((a: any, i: number) => {
            const text = safeLatex(a?.text);
            const isSelected = selected === i;

            return (
              <button
                key={i}
                className={`btn btn-sm w-auto ${
                  isSelected
                    ? isCorrect
                      ? "btn-success"
                      : "btn-danger"
                    : "btn-outline-primary"
                }`}
                style={{ minWidth: "90px" }}
                onClick={() => handleAnswerClick(i, a)}
              >
                <Latex>{text}</Latex>
              </button>
            );
          })}
        </div>
      )}

      {selected !== null && (
        <div className="mt-3" style={{ fontWeight: "bold", fontSize: 18 }}>
          {isCorrect ? "Correct!" : "Incorrect — try again"}
        </div>
      )}

      {selected !== null && !isCorrect && solution && (
        <>
          <div
            className="mt-2 p-2"
            style={{
              background: "#f8f9fa",
              borderLeft: "4px solid #dc3545",
              fontSize: 15,
              whiteSpace: "pre-wrap",
            }}
          >
            <Latex>{solution}</Latex>
          </div>

          {mode === "student" && backendResult && (
                <>
                  <button
                    className="btn btn-primary mt-2"
                    onClick={() => onStudentNext?.(backendResult)}
                  >
                    Next
                  </button>
                  <button
                    className="btn btn-sm btn-warning mt-2 ms-2"
                    onClick={handleIDontGetIt}
                  >
                    I don't get it
                  </button>
                </>
              )}
        </>
      )}

      {flagged && (
        <div className="alert alert-info mt-2 p-2">
          Added to tutor review list
        </div>
      )}
    </div>
  );
}