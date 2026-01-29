import json

def format_for_editor(obj: dict) -> str:
    lines = []
    for key, value in obj.items():
        # Convert nested objects or lists to strings cleanly
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value, indent=2)
        else:
            value_str = str(value)

        # Format with newline + tab indentation
        lines.append(f"{key}:\n    {value_str}")
    return "\n\n".join(lines)
