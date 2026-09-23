/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { JobOfferRead } from "./JobOfferRead";
export type JobMatchResponse = {
  job_offer: JobOfferRead;
  score: number;
  matching_skills?: Array<string>;
  missing_skills?: Array<string>;
};
