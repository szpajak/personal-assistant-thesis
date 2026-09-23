/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { JobOfferRead } from "./JobOfferRead";
export type ApplicationRead = {
  job_offer_id: string;
  status: string;
  applied_at?: string | null;
  notes?: string | null;
  id: string;
  job_offer?: JobOfferRead | null;
};
