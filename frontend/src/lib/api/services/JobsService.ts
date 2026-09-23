/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { JobMatchResponse } from "../models/JobMatchResponse";
import type { JobOfferRead } from "../models/JobOfferRead";
import type { JobPromoteResponse } from "../models/JobPromoteResponse";
import type { JobScrapeRequest } from "../models/JobScrapeRequest";
import type { JobScrapeTaskResponse } from "../models/JobScrapeTaskResponse";
import type { CancelablePromise } from "../core/CancelablePromise";
import { OpenAPI } from "../core/OpenAPI";
import { request as __request } from "../core/request";
export class JobsService {
  /**
   * List Jobs
   * @param source
   * @param status
   * @param search
   * @param tier
   * @param token
   * @param authToken
   * @returns JobOfferRead Successful Response
   * @throws ApiError
   */
  public static listJobsApiV1JobsGet(
    source?: string | null,
    status?: string | null,
    search?: string | null,
    tier?: string | null,
    token?: string | null,
    authToken?: string | null,
  ): CancelablePromise<Array<JobOfferRead>> {
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/jobs/",
      cookies: {
        auth_token: authToken,
      },
      query: {
        source: source,
        status: status,
        search: search,
        tier: tier,
        token: token,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Match Jobs
   * @param token
   * @param authToken
   * @returns JobMatchResponse Successful Response
   * @throws ApiError
   */
  public static matchJobsApiV1JobsMatchGet(
    token?: string | null,
    authToken?: string | null,
  ): CancelablePromise<Array<JobMatchResponse>> {
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/jobs/match",
      cookies: {
        auth_token: authToken,
      },
      query: {
        token: token,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Trigger Job Scrape
   * Queue a background scrape using the filters supplied by the app.
   * @param requestBody
   * @param token
   * @param authToken
   * @returns JobScrapeTaskResponse Successful Response
   * @throws ApiError
   */
  public static triggerJobScrapeApiV1JobsScrapePost(
    requestBody: JobScrapeRequest,
    token?: string | null,
    authToken?: string | null,
  ): CancelablePromise<JobScrapeTaskResponse> {
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/jobs/scrape",
      cookies: {
        auth_token: authToken,
      },
      query: {
        token: token,
      },
      body: requestBody,
      mediaType: "application/json",
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Promote Job
   * Promote a scraped JobListing into the career knowledge graph.
   * @param jobId
   * @param token
   * @param authToken
   * @returns JobPromoteResponse Successful Response
   * @throws ApiError
   */
  public static promoteJobApiV1JobsJobIdPromotePost(
    jobId: string,
    token?: string | null,
    authToken?: string | null,
  ): CancelablePromise<JobPromoteResponse> {
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/jobs/{job_id}/promote",
      path: {
        job_id: jobId,
      },
      cookies: {
        auth_token: authToken,
      },
      query: {
        token: token,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
