import apiDev from './api-dev';
import { llmConnectionsEndpoints } from 'utils/endpoints';
import { removeCommasFromNumber } from 'utils/commonUtils';
import { maskSensitiveKey } from 'utils/llmConnectionsUtils';

export interface LLMConnection {
  id: number;
  connectionName: string;
  llmPlatform: string;
  llmModel: string;
  embeddingPlatform: string;
  embeddingModel: string;
  monthlyBudget: number;
  warnBudgetThreshold: number;
  stopBudgetThreshold: number;
  disconnectOnBudgetExceed: boolean;
  environment: string;
  connectionStatus: 'active' | 'inactive';
  createdAt: string;
  updatedAt: string;
  totalPages?: number;
  budgetStatus: 'within_budget' | 'over_budget' | 'close_to_exceed';
  usedBudget?: number;
  // Azure credentials
  deploymentName?: string;
  targetUri?: string;
  apiKey?: string;
  // AWS Bedrock credentials
  secretKey?: string;
  accessKey?: string;
  // Embedding model credentials
  embeddingModelApiKey?: string;
}

export interface LLMConnectionsResponse {
  data: LLMConnection[];

}

export interface BudgetStatus {
  used_budget_percentage: number;
  exceeded_stop_budget: boolean;
  exceeded_warn_budget: boolean;
  data: {
    id: number;
    connectionName: string;
    usedBudget: number;
    monthlyBudget: number;
    warnBudgetThreshold: number;
    stopBudgetThreshold: number;
    environment: string;
    connectionStatus: string;
    createdAt: string;
    llmPlatform: string;
    llmModel: string;
    embeddingPlatform: string;
    embeddingModel: string;
  }
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
  connectionName: string;
  llmPlatform: string;
  llmModel: string;
  embeddingModelPlatform: string;
  embeddingModel: string;
  monthlyBudget: string;
  warnBudget: string;
  stopBudget: string;
  disconnectOnBudgetExceed: boolean;
  deploymentEnvironment: string;
  // Azure credentials
  deploymentName?: string;
  targetUri?: string;
  apiKey?: string;
  // AWS Bedrock credentials
  secretKey?: string;
  accessKey?: string;
  // Embedding model credentials
  embeddingModelApiKey?: string;
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

export async function getProductionConnection(): Promise<LLMConnection | null> {
  const { data } = await apiDev.get(llmConnectionsEndpoints.GET_PRODUCTION_CONNECTION());
  return data?.response?.[0] || null;
}


export async function createLLMConnection(connectionData: LLMConnectionFormData): Promise<LLMConnection> {
  const { data } = await apiDev.post(llmConnectionsEndpoints.CREATE_LLM_CONNECTION(), {
    connection_name: connectionData.connectionName,
    llm_platform: connectionData.llmPlatform,
    llm_model: connectionData.llmModel,
    embedding_platform: connectionData.embeddingModelPlatform,
    embedding_model: connectionData.embeddingModel,
    monthly_budget: parseFloat(removeCommasFromNumber(connectionData.monthlyBudget)),
    warn_budget_threshold: parseInt(connectionData.warnBudget),
    stop_budget_threshold: connectionData.disconnectOnBudgetExceed ? parseInt(connectionData.stopBudget) : 0,
    disconnect_on_budget_exceed: connectionData.disconnectOnBudgetExceed,
    deployment_environment: connectionData.deploymentEnvironment.toLowerCase(),
    // Azure credentials
    deployment_name: connectionData.deploymentName || "",
    target_uri: connectionData.targetUri || "",
    api_key: maskSensitiveKey(connectionData.apiKey) || "",
    // AWS Bedrock credentials
    secret_key: maskSensitiveKey(connectionData.secretKey) || "",
    access_key: maskSensitiveKey(connectionData.accessKey) || "",
    // Embedding model credentials
    embedding_model_api_key: maskSensitiveKey(connectionData.embeddingModelApiKey) || "",
  });
  return data?.response;
}

export async function updateLLMConnection(
  id: string | number,
  connectionData: LLMConnectionFormData
): Promise<LLMConnection> {
  const { data } = await apiDev.post(llmConnectionsEndpoints.UPDATE_LLM_CONNECTION(), {
    connection_id: id,
    connection_name: connectionData.connectionName,
    llm_platform: connectionData.llmPlatform,
    llm_model: connectionData.llmModel,
    embedding_platform: connectionData.embeddingModelPlatform,
    embedding_model: connectionData.embeddingModel,
    monthly_budget: parseFloat(removeCommasFromNumber(connectionData.monthlyBudget)),
    warn_budget_threshold: parseInt(connectionData.warnBudget),
    stop_budget_threshold: connectionData.disconnectOnBudgetExceed ? parseInt(connectionData.stopBudget) : 0,
    disconnect_on_budget_exceed: connectionData.disconnectOnBudgetExceed,
    deployment_environment: connectionData.deploymentEnvironment.toLowerCase(),
    // Azure credentials
    deployment_name: connectionData.deploymentName || "",
    target_uri: connectionData.targetUri || "",
    api_key: maskSensitiveKey(connectionData.apiKey) || "",
    // AWS Bedrock credentials
    secret_key: maskSensitiveKey(connectionData.secretKey) || "",
    access_key: maskSensitiveKey(connectionData.accessKey) || "",
    // Embedding model credentials
    embedding_model_api_key: maskSensitiveKey(connectionData.embeddingModelApiKey) || "",
  });
  return data?.response;
}

export async function deleteLLMConnection(id: string | number): Promise<void> {
  await apiDev.post(llmConnectionsEndpoints.DELETE_LLM_CONNECTION(), {
    connection_id: id,
  });
}

export async function checkBudgetStatus(): Promise<BudgetStatus | null> {
  try {
    const { data } = await apiDev.get(llmConnectionsEndpoints.CHECK_BUDGET_STATUS());
    return data?.response as BudgetStatus;
  } catch (error) {
    // Return null if no production connection found (404) or other errors
    return null;
  }
}

export async function updateLLMConnectionStatus(
  id: string | number, 
  status: 'active' | 'inactive'
): Promise<LLMConnection> {
  const { data } = await apiDev.post(llmConnectionsEndpoints.UPDATE_LLM_CONNECTION_STATUS(), {
    connection_id: id,
    connection_status: status,
  });
  return data?.response;
}
