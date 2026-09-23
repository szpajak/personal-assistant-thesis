/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CancelablePromise } from "../core/CancelablePromise";
import { OpenAPI } from "../core/OpenAPI";
import { request as __request } from "../core/request";
export class EmailService {
  /**
   * Sync Emails
   * Poll inbox for new emails and process them.
   * @param token
   * @param authToken
   * @returns any Successful Response
   * @throws ApiError
   */
  public static syncEmailsApiV1EmailSyncPost(
    token?: string | null,
    authToken?: string | null,
  ): CancelablePromise<Array<Record<string, any>>> {
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/email/sync",
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
