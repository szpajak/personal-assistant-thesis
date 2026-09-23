/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CancelablePromise } from "../core/CancelablePromise";
import { OpenAPI } from "../core/OpenAPI";
import { request as __request } from "../core/request";
export class KnowledgeGraphService {
  /**
   * Get Stats
   * Get dashboard statistics for a person.
   * @param token
   * @param authToken
   * @returns any Successful Response
   * @throws ApiError
   */
  public static getStatsApiV1KgStatsGet(
    token?: string | null,
    authToken?: string | null,
  ): CancelablePromise<Record<string, any>> {
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/kg/stats",
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
   * Get Graph
   * Get the full knowledge graph for a person.
   * @param token
   * @param authToken
   * @returns any Successful Response
   * @throws ApiError
   */
  public static getGraphApiV1KgGraphGet(
    token?: string | null,
    authToken?: string | null,
  ): CancelablePromise<Record<string, any>> {
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/kg/graph",
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
