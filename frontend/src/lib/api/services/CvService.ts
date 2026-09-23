/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CancelablePromise } from "../core/CancelablePromise";
import { OpenAPI } from "../core/OpenAPI";
import { request as __request } from "../core/request";
export class CvService {
  /**
   * Generate Cv
   * Generate a personalized CV for a specific job offer.
   * @param jobId Job Offer ID to tailor the CV for
   * @param token
   * @param authToken
   * @returns string Successful Response
   * @throws ApiError
   */
  public static generateCvApiV1CvGeneratePost(
    jobId: string,
    token?: string | null,
    authToken?: string | null,
  ): CancelablePromise<Record<string, string>> {
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/cv/generate",
      cookies: {
        auth_token: authToken,
      },
      query: {
        job_id: jobId,
        token: token,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Download Cv
   * Download a personalized CV as a PDF.
   * @param jobId Job Offer ID
   * @param token
   * @param authToken
   * @returns any Successful Response
   * @throws ApiError
   */
  public static downloadCvApiV1CvDownloadGet(
    jobId: string,
    token?: string | null,
    authToken?: string | null,
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/cv/download",
      cookies: {
        auth_token: authToken,
      },
      query: {
        job_id: jobId,
        token: token,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
