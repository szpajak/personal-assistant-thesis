/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SkillDraft } from "./SkillDraft";
export type ProjectRead = {
  title: string;
  description: string;
  tech_stack?: Array<string>;
  start_date: string;
  end_date?: string | null;
  media_urls?: Array<string>;
  seniority?: string | null;
  achievements?: Array<string>;
  skills?: Array<SkillDraft>;
  skip_enrichment?: boolean;
  id: string;
};
