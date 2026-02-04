import React from "react";
import katex from "katex";
import "katex/dist/katex.min.css";

interface LatexProps {
  children: string;
}

export function Latex({ children }: LatexProps) {
  // Split into text and math segments
  // Captures $...$ and $$...$$ as separate tokens
  const parts = children.split(/(\${1,2}[\s\S]*?\${1,2})/g);

  return (
    <>
      {parts.map((part, i) => {
        const trimmed = part.trim();

        // Block math: $$ ... $$
        if (trimmed.startsWith("$$") && trimmed.endsWith("$$")) {
          const content = trimmed.slice(2, -2);
          try {
            const html = katex.renderToString(content, {
              displayMode: true,
              throwOnError: true,
            });
            return (
              <span
                key={i}
                dangerouslySetInnerHTML={{ __html: html }}
              />
            );
          } catch (err: any) {
            return (
              <span key={i} style={{ color: "red", fontFamily: "monospace" }}>
                LaTeX error: {err.message}
              </span>
            );
          }
        }

        // Inline math: $ ... $
        if (trimmed.startsWith("$") && trimmed.endsWith("$")) {
          const content = trimmed.slice(1, -1);
          try {
            const html = katex.renderToString(content, {
              displayMode: false,
              throwOnError: true,
            });
            return (
              <span
                key={i}
                dangerouslySetInnerHTML={{ __html: html }}
              />
            );
          } catch (err: any) {
            return (
              <span key={i} style={{ color: "red", fontFamily: "monospace" }}>
                LaTeX error: {err.message}
              </span>
            );
          }
        }

        // Plain text — preserve spaces and newlines
        return (
          <span key={i} style={{ whiteSpace: "pre-wrap" }}>
            {part}
          </span>
        );
      })}
    </>
  );
}