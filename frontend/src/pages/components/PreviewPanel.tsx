import { useState } from "react";
import { Latex } from "./Latex";
import "katex/dist/katex.min.css";
import { apiFetch, apiFetchJson } from "../../utils/apiFetch"

interface PreviewPanelProps {
  preview: any;
  templateContent: string;
  onNext: (newPreview: any) => void;
}

export function PreviewPanel({preview, templateContent, onNext,}: PreviewPanelProps) {
  const [selected, setSelected] = useState<number | null>(null);
  const [isCorrect, setIsCorrect] = useState<boolean | null>(null);
  const [flagged, setFlagged] = useState(false);

  // -------------------------------------------------------
  // Utility: always return a safe string for <Latex>
  // -------------------------------------------------------
  const safeLatex = (value: any): string => {
    if (value === null || value === undefined) return "";
    if (typeof value === "string" || typeof value === "number") return String(value);
    try {
      return JSON.stringify(value);
    } catch {
      return "";
    }
  };

  // -------------------------------------------------------
  // Load next question
  // -------------------------------------------------------
  async function loadNextQuestion() {
    const res = await apiFetch("/api/templates/preview/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: templateContent }),
    });

    const data = await res.json();

    setSelected(null);
    setIsCorrect(null);

    onNext(data.preview);
  }

  // -------------------------------------------------------
  // Student flags question
  // -------------------------------------------------------
  async function handleIDontGetIt() {
    setFlagged(true);

    setTimeout(() => {
      setFlagged(false);
      loadNextQuestion();
    }, 1500);

    console.log("Student flagged this question:", preview);
  }

  // -------------------------------------------------------
  // Early return: no preview yet
  // -------------------------------------------------------
  if (!preview) {
    return (
      <div style={{ padding: 12, color: "#888" }}>
        Start typing to see a live preview…
      </div>
    );
  }

  // -------------------------------------------------------
  // Backend errors (debug mode)
  // -------------------------------------------------------
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

        {/* Show partial preview if available */}
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

  // -------------------------------------------------------
  // Extract preview fields safely
  // -------------------------------------------------------
  const question = safeLatex(preview.question);
  const solution = safeLatex(preview.solution);
  const answers = Array.isArray(preview.answers) ? preview.answers : [];
  const diagramSvg = preview.diagram_svg;

  // -------------------------------------------------------
  // Handle answer click
  // -------------------------------------------------------
  function handleAnswerClick(index: number, answer: any) {
    setSelected(index);

    const correct = Boolean(answer.correct);
    setIsCorrect(correct);

    if (correct) {
      setTimeout(() => {
        loadNextQuestion();
      }, 1000);
    }
  }

  // -------------------------------------------------------
  // Render
  // -------------------------------------------------------
  return (
    <div style={{ padding: 12, fontSize: 18 }}>
      {/* Question */}
      <div style={{ marginBottom: 12, fontWeight: "bold" }}>
        <Latex>{question}</Latex>
      </div>

      {/* Diagram */}
      {diagramSvg && (
        <div style={{ display: "flex", justifyContent: "center", width: "100%" }}>
          <div dangerouslySetInnerHTML={{ __html: diagramSvg }} />
        </div>
      )}

      {/* Answers */}
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

      {/* Correct / Incorrect message */}
      {selected !== null && (
        <div className="mt-3" style={{ fontWeight: "bold", fontSize: 18 }}>
          {isCorrect ? "Correct!" : "Incorrect — try again"}
        </div>
      )}

      {/* Incorrect: show solution + buttons */}
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

          <button className="btn btn-sm btn-primary mt-2" onClick={loadNextQuestion}>
            Next
          </button>

          <button
            className="btn btn-sm btn-warning mt-2 ms-2"
            onClick={handleIDontGetIt}
          >
            I don’t get it
          </button>
        </>
      )}

      {/* Flagged message */}
      {flagged && (
        <div className="alert alert-info mt-2 p-2">
          Added to tutor review list
        </div>
      )}
    </div>
  );
}