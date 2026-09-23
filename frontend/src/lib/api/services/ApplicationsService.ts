/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ApplicationCreate } from "../models/ApplicationCreate";
import type { ApplicationRead } from "../models/ApplicationRead";
import type { ApplicationUpdate } from "../models/ApplicationUpdate";
import type { CancelablePromise } from "../core/CancelablePromise";
import { OpenAPI } from "../core/OpenAPI";
import { request as __request } from "../core/request";
export class ApplicationsService {
  /**
   * List Applications
   * @param token
   * @param authToken
   * @returns ApplicationRead Successful Response
   * @throws ApiError
   */
  public static listApplicationsApiV1ApplicationsGet(
    token?: string | null,
    authToken?: string | null,
  ): CancelablePromise<Array<ApplicationRead>> {
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/applications/",
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
   * Create Application
   * @param requestBody
   * @param token
   * @param authToken
   * @returns ApplicationRead Successful Response
   * @throws ApiError
   */
  public static createApplicationApiV1ApplicationsPost(
    requestBody: ApplicationCreate,
    token?: string | null,
    authToken?: string | null,
  ): CancelablePromise<ApplicationRead> {
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/applications/",
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
   * Update Application
   * @param id
   * @param requestBody
   * @param token
   * @param authToken
   * @returns ApplicationRead Successful Response
   * @throws ApiError
   */
  public static updateApplicationApiV1ApplicationsIdPatch(
    id: string,
    requestBody: ApplicationUpdate,
    token?: string | null,
    authToken?: string | null,
  ): CancelablePromise<ApplicationRead> {
    return __request(OpenAPI, {
      method: "PATCH",
      url: "/api/v1/applications/{id}",
      path: {
        id: id,
      },
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
}
