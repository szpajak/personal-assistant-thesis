/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SkillCreate } from "../models/SkillCreate";
import type { SkillDemand } from "../models/SkillDemand";
import type { SkillRead } from "../models/SkillRead";
import type { CancelablePromise } from "../core/CancelablePromise";
import { OpenAPI } from "../core/OpenAPI";
import { request as __request } from "../core/request";
export class SkillsService {
  /**
   * List Skills
   * @param token
   * @param authToken
   * @returns SkillRead Successful Response
   * @throws ApiError
   */
  public static listSkillsApiV1SkillsGet(
    token?: string | null,
    authToken?: string | null,
  ): CancelablePromise<Array<SkillRead>> {
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/skills/",
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
   * Add Skill
   * @param requestBody
   * @param token
   * @param authToken
   * @returns SkillRead Successful Response
   * @throws ApiError
   */
  public static addSkillApiV1SkillsPost(
    requestBody: SkillCreate,
    token?: string | null,
    authToken?: string | null,
  ): CancelablePromise<SkillRead> {
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/skills/",
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
   * Get Skill Analysis
   * @param token
   * @param authToken
   * @returns any Successful Response
   * @throws ApiError
   */
  public static getSkillAnalysisApiV1SkillsAnalysisGet(
    token?: string | null,
    authToken?: string | null,
  ): CancelablePromise<Record<string, any>> {
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/skills/analysis",
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
   * Get Market Demand
   * @param limit Maximum number of skills to return
   * @param token
   * @param authToken
   * @returns SkillDemand Successful Response
   * @throws ApiError
   */
  public static getMarketDemandApiV1SkillsMarketDemandGet(
    limit: number = 10,
    token?: string | null,
    authToken?: string | null,
  ): CancelablePromise<Array<SkillDemand>> {
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/skills/market-demand",
      cookies: {
        auth_token: authToken,
      },
      query: {
        limit: limit,
        token: token,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
