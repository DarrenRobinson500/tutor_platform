export type TemplateSummary = {
  id: number;
  name: string;
  description: string;
  subject: string;
  topic: string;
  status: string;
  updated_at: string;
};

export type TemplateMetadata = {
  id: number | null;
  name: string;
  description: string;
  subject: string;
  topic: string;
  subtopic: string;
  difficulty: string;
  tags: string[];
  curriculum: any[];
  status: string;
  version: number;
  skill: number | null;
}

export const emptyMetadata: TemplateMetadata = {
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

