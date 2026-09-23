/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type JobOfferRead = {
  id: string;
  title: string;
  company: string;
  url: string;
  description: string;
  required_skills: Array<string>;
  scraped_at: string;
  tier?: "staging" | "career";
};
