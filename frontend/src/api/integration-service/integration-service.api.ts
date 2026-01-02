import { openHands } from "../open-hands-axios";
import {
  GitLabResourcesResponse,
  ReinstallWebhookRequest,
  ResourceIdentifier,
  ResourceInstallationResult,
} from "./integration-service.types";

export class IntegrationService {
  /**
   * Get all GitLab projects and groups where the user has admin access
   * @returns Promise with list of resources and their webhook status
   */
  static async getGitLabResources(): Promise<GitLabResourcesResponse> {
    const { data } = await openHands.get<GitLabResourcesResponse>(
      "/integration/gitlab/resources",
    );
    return data;
  }

  /**
   * Reinstall webhook on a specific GitLab resource
   * @param resource - Resource to reinstall webhook on
   * @returns Promise with installation result
   */
  static async reinstallGitLabWebhook(
    resource: ResourceIdentifier,
  ): Promise<ResourceInstallationResult> {
    const requestBody: ReinstallWebhookRequest = { resource };
    const { data } = await openHands.post<ResourceInstallationResult>(
      "/integration/gitlab/reinstall-webhook",
      requestBody,
    );
    return data;
  }
}
