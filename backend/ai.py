
import os
import json
import re
import time
from openai import OpenAI

def extract_json(text: str):
    if not text or not text.strip():
        raise ValueError("AI returned empty response")

    # Remove markdown fences
    text = text.strip()
    text = re.sub(r"^```json", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"^```", "", text).strip()
    text = re.sub(r"```$", "", text).strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to extract the first {...} block
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from AI output:\n{text}")


# print(os.environ.get("OPENAI_API_KEY"))

PROMPT_INSTRUCTIONS = """
Each template must be returned as an item in a JSON array.
Each item represents ONE template.

Each template MUST follow this structure exactly:

{
  "title": "...",
  "years": <k - 12>
  "difficulty": <easy, medium, hard>
  "introduction": "...",
  "worked_example": {
    "example_number": <number>,
    "steps": ["...", "..."]
  },
  "parameters": {
    "<param_name>": {
      "type": "int" | "float",
      "min": <number>,        // for int
      "max": <number>,        // for int
    },
    ...
  },
  "question": {
    "text": "A question using parameters like {{ a }}, {{ b }}, {{ x }}."
  },
  "answers": [
    { "int": "{{ a }} * {{ b }}", "correct": true },
    { "int": "{{ a }}", "correct": false },
    { "int": "{{ b }}", "correct": false },
    { "int": "{{ a }} / {{ b }}", "correct": false }
  ],
  "solution": {
    "text": "A worked solution using the same parameters, also wrapped in {{ }}."
  },
  "diagram": {
    "type": "none",
    "elements": []
  },
  "validation": {
    "required_fields": ["question.text", "answers", "solution.text"],
    "rules": [
      { "check": "a != 0", "message": "Coefficient 'a' must not be zero." }
    ]
  }
}

STRICT RULES:
- Every parameter used in question, answers, or solution MUST be declared in the "parameters" block.
- Every parameter reference MUST be wrapped in double curly braces, e.g. {{ a }}, {{ b }}, {{ x }}.
- Parameters should not be given a particular, but rather a range so that the can be randomised.
- A correct answer should be provided.
- Three incorrect parameterised answers should be provided reflecting common mistakes made for this type of question. 
- No raw numbers should appear where a parameter should be used.
- Provide exactly 5 easy templates.
- Provide exactly 5 medium templates.
- Provide exactly 5 hard templates.
- Return ONLY valid JSON. No markdown fences. No commentary.
"""


# api_key=os.environ["OPENAI_API_KEY"]
chat_key=os.environ["CHAT_KEY"]
# print("Chat key:", chat_key)

client = OpenAI(api_key=chat_key)

def generate_template_content(skill_description: str, grade) -> dict:
    # print("Chat key:", chat_key)
    prompt = f"You are an expert NSW mathematics tutor. Create a structured practice template for the skill: '{skill_description}' and for the grade: '{grade}'.\n" + PROMPT_INSTRUCTIONS

    start_time = time.time()

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        # model="gpt-5.2",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )

    end_time = time.time()
    duration = end_time - start_time
    print(f"Time taken: {duration:.2f} seconds")



    raw = response.choices[0].message.content
    print(raw)
    return extract_json(raw)

