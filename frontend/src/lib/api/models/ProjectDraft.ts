/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SkillDraft } from "./SkillDraft";
export type ProjectDraft = {
  title: string;
  description: string;
  skills?: Array<SkillDraft>;
  tech_stack?: Array<string>;
  start_date?: string | null;
  end_date?: string | null;
  media_urls?: Array<string>;
  achievements?: Array<string>;
  seniority?: string | null;
  source?: string;
};
