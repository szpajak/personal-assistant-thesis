/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { Body_login_api_v1_auth_login_post } from "../models/Body_login_api_v1_auth_login_post";
import type { Token } from "../models/Token";
import type { UserCreate } from "../models/UserCreate";
import type { UserRead } from "../models/UserRead";
import type { CancelablePromise } from "../core/CancelablePromise";
import { OpenAPI } from "../core/OpenAPI";
import { request as __request } from "../core/request";
export class AuthenticationService {
  /**
   * Get Me
   * Get the current logged in user.
   * @param token
   * @param authToken
   * @returns UserRead Successful Response
   * @throws ApiError
   */
  public static getMeApiV1AuthMeGet(
    token?: string | null,
    authToken?: string | null,
  ): CancelablePromise<UserRead> {
    return __request(OpenAPI, {
      method: "GET",
      url: "/api/v1/auth/me",
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
   * Register
   * Register a new user and set auth cookie.
   * @param requestBody
   * @returns UserRead Successful Response
   * @throws ApiError
   */
  public static registerApiV1AuthRegisterPost(
    requestBody: UserCreate,
  ): CancelablePromise<UserRead> {
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/auth/register",
      body: requestBody,
      mediaType: "application/json",
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Login
   * Login and set auth cookie.
   * @param requestBody
   * @returns Token Successful Response
   * @throws ApiError
   */
  public static loginApiV1AuthLoginPost(
    requestBody: Body_login_api_v1_auth_login_post,
  ): CancelablePromise<Token> {
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/auth/login",
      body: requestBody,
      mediaType: "application/json",
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Logout
   * Clear the auth cookie.
   * @returns any Successful Response
   * @throws ApiError
   */
  public static logoutApiV1AuthLogoutPost(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/auth/logout",
    });
  }
}
