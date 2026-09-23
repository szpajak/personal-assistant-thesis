/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { Body_upload_project_document_api_v1_portfolio_upload_post } from "../models/Body_upload_project_document_api_v1_portfolio_upload_post";
import type { ProjectCreate } from "../models/ProjectCreate";
import type { ProjectExtractResponse } from "../models/ProjectExtractResponse";
import type { ProjectRead } from "../models/ProjectRead";
import type { CancelablePromise } from "../core/CancelablePromise";
import { OpenAPI } from "../core/OpenAPI";
import { request as __request } from "../core/request";
export class PortfolioService {
  /**
   * List Portfolio
   * @param token
   * @param authToken
   * @returns ProjectRead Successful Response
   * @throws ApiError
   */
  public static listPortfolioApiV1PortfolioGet(
    token?: string | null,
    authToken?: string | null,
  ): CancelablePromise<Array<ProjectRead>> {
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/portfolio/",
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
   * Create Project
   * @param requestBody
   * @param token
   * @param authToken
   * @returns ProjectRead Successful Response
   * @throws ApiError
   */
  public static createProjectApiV1PortfolioPost(
    requestBody: ProjectCreate,
    token?: string | null,
    authToken?: string | null,
  ): CancelablePromise<ProjectRead> {
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/portfolio/",
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
   * Create Project From Plan
   * Create an in-progress project from a learning plan item.
   * @param requestBody
   * @param token
   * @param authToken
   * @returns ProjectRead Successful Response
   * @throws ApiError
   */
  public static createProjectFromPlanApiV1PortfolioFromPlanPost(
    requestBody: Record<string, any>,
    token?: string | null,
    authToken?: string | null,
  ): CancelablePromise<ProjectRead> {
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/portfolio/from-plan",
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
   * Upload Project Document
   * Extract project draft(s) from an uploaded document for user review.
   *
   * Nothing is written to the knowledge graph here - the caller must review
   * the returned draft(s) and submit each confirmed one via `POST /` (with
   * `skip_enrichment=True`) to actually create the project.
   * @param formData
   * @param token
   * @param authToken
   * @returns ProjectExtractResponse Successful Response
   * @throws ApiError
   */
  public static uploadProjectDocumentApiV1PortfolioUploadPost(
    formData: Body_upload_project_document_api_v1_portfolio_upload_post,
    token?: string | null,
    authToken?: string | null,
  ): CancelablePromise<ProjectExtractResponse> {
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/portfolio/upload",
      cookies: {
        auth_token: authToken,
      },
      query: {
        token: token,
      },
      formData: formData,
      mediaType: "multipart/form-data",
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
