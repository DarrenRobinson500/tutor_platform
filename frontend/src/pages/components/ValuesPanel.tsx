type ValuesPanelProps = {
  substitutedYaml: string | null;
};

export function ValuesPanel({ substitutedYaml }: ValuesPanelProps) {
  return (
    <pre
      style={{
        whiteSpace: "pre-wrap",
        fontFamily: "monospace",
        fontSize: "0.85rem",
        margin: 0,
      }}
    >
      {substitutedYaml || "No values yet. Make a change in the editor to see evaluated YAML."}
    </pre>
  );
}