/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type JobTypeFilter = "fulltime" | "parttime" | "internship" | "contract";

/**
 * Filters forwarded to jobspy2 scrape_jobs for an on-demand search.
 */
export type JobScrapeRequest = {
  /**
   * Job title / keywords
   */
  search_term: string;
  /**
   * City, region, or country string (e.g. 'Warsaw, Poland')
   */
  location?: string | null;
  /**
   * Indeed/Glassdoor country (e.g. 'Poland', 'USA', 'UK', 'Germany')
   */
  country?: string | null;
  /**
   * Job boards to scrape (linkedin, indeed, glassdoor, zip_recruiter, google)
   */
  sites?: Array<string> | null;
  /**
   * Employment type filter supported by jobspy2
   */
  job_type?: JobTypeFilter | null;
  /**
   * Prefer remote listings
   */
  is_remote?: boolean;
  /**
   * Only jobs posted within the last N hours
   */
  hours_old?: number | null;
  /**
   * Search radius in miles around location
   */
  distance?: number | null;
  /**
   * Max results to fetch per site (capped for rate limiting)
   */
  results_wanted?: number | null;
  /**
   * Also pull the unfiltered RemoteOK feed
   */
  include_remoteok?: boolean;
};
