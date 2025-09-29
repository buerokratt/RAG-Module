import apiDev from './api-dev';
import { llmConnectionsEndpoints } from 'utils/endpoints';
import { removeCommasFromNumber } from 'utils/commonUtilts';

export interface LLMConnection {
  id: number;
  llmPlatform: string;
  llmModel: string;
  embeddingPlatform: string;
  embeddingModel: string;
  monthlyBudget: number;
  environment: string;
  status: string;
  createdAt: string;
  updatedAt: string;
  totalPages?: number;
  budgetStatus: 'within_budget' | 'over_budget' | 'close_to_exceed';
  usedBudget?: number; 

}

export interface LLMConnectionsResponse {
  data: LLMConnection[];
  
}

export interface LLMConnectionFilters {
  pageNumber?: number;
  pageSize?: number;
  sortBy?: string;
  sortOrder?: string;
  llmPlatform?: string;
  llmModel?: string;
  embeddingPlatform?: string;
  environment?: string;
  status?: string;
}

// Legacy interface for backwards compatibility
export interface LegacyLLMConnectionFilters {
  page: number;
  pageSize: number;
  sorting?: string;
  llmPlatform?: string;
  embeddingPlatform?: string;
  environment?: string;
  status?: string;
}

export interface LLMConnectionFormData {
  llmPlatform: string;
  llmModel: string;
  embeddingModelPlatform: string;
  embeddingModel: string;
  llmApiKey: string;
  embeddingApiKey: string;
  monthlyBudget: string;
  deploymentEnvironment: string;
}

export async function fetchLLMConnectionsPaginated(filters: LLMConnectionFilters): Promise<LLMConnection[]> {
  const queryParams = new URLSearchParams();
  
  if (filters.pageNumber) queryParams.append('pageNumber', filters.pageNumber.toString());
  if (filters.pageSize) queryParams.append('pageSize', filters.pageSize.toString());
  if (filters.sortBy) queryParams.append('sortBy', filters.sortBy);
  if (filters.sortOrder) queryParams.append('sortOrder', filters.sortOrder);
  if (filters.llmPlatform) queryParams.append('llmPlatform', filters.llmPlatform);
  if (filters.llmModel) queryParams.append('llmModel', filters.llmModel);
  if (filters.environment) queryParams.append('environment', filters.environment);
  
  const url = `${llmConnectionsEndpoints.FETCH_LLM_CONNECTIONS_PAGINATED()}?${queryParams.toString()}`;
  const { data } = await apiDev.get(url);
  return data?.response;
}

export async function getLLMConnection(id: string | number): Promise<LLMConnection> {
  const { data } = await apiDev.post(llmConnectionsEndpoints.GET_LLM_CONNECTION(), {
    connection_id: id,
  });
  return data?.response;
}

export async function createLLMConnection(connectionData: LLMConnectionFormData): Promise<LLMConnection> {
  const { data } = await apiDev.post(llmConnectionsEndpoints.CREATE_LLM_CONNECTION(), {
    llm_platform: connectionData.llmPlatform,
    llm_model: connectionData.llmModel,
    llm_api_key: connectionData.llmApiKey,
    embedding_platform: connectionData.embeddingModelPlatform,
    embedding_model: connectionData.embeddingModel,
    embedding_api_key: connectionData.embeddingApiKey,
    monthly_budget: parseFloat(removeCommasFromNumber(connectionData.monthlyBudget)),
    deployment_environment: connectionData.deploymentEnvironment.toLowerCase(),
  });
  return data?.response;
}

export async function updateLLMConnection(
  id: string | number, 
  connectionData: LLMConnectionFormData
): Promise<LLMConnection> {
  const { data } = await apiDev.post(llmConnectionsEndpoints.UPDATE_LLM_CONNECTION(), {
    connection_id: id,
    llm_platform: connectionData.llmPlatform,
    llm_model: connectionData.llmModel,
    llm_api_key: connectionData.llmApiKey,
    embedding_platform: connectionData.embeddingModelPlatform,
    embedding_model: connectionData.embeddingModel,
    embedding_api_key: connectionData.embeddingApiKey,
    monthly_budget: parseFloat(removeCommasFromNumber(connectionData.monthlyBudget)),
    deployment_environment: connectionData.deploymentEnvironment.toLowerCase(),
  });
  return data?.response;
}

export async function deleteLLMConnection(id: string | number): Promise<void> {
  await apiDev.post(llmConnectionsEndpoints.DELETE_LLM_CONNECTION(), {
    connection_id: id,
  });
}
