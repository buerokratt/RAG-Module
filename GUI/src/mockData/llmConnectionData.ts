export interface LLMConnectionData {
  llmConnectionId: number | string;
  llmConnectionName?: string;
  datasetVersion?: string;
  platform?: string;
  model?: boolean;
  isActive?: boolean;
  deploymentEnv?: string;
  budgetStatus?: string;
  // Form data for detailed view
  llmPlatform?: string;
  llmModel?: string;
  embeddingModelPlatform?: string;
  embeddingModel?: string;
  llmApiKey?: string;
  embeddingApiKey?: string;
  monthlyBudget?: string;
  deploymentEnvironment?: string;
}

export const mockLLMConnections: LLMConnectionData[] = [
  {
    llmConnectionId: 1,
    llmConnectionName: "OpenAI GPT-4 Connection",
    datasetVersion: "v2.1.0",
    platform: "OpenAI",
    model: true,
    isActive: true,
    deploymentEnv: "Production",
    budgetStatus: "within"
  },
  {
    llmConnectionId: 2,
    llmConnectionName: "Claude 3 Sonnet Integration",
    datasetVersion: "v1.8.5",
    platform: "Anthropic",
    model: true,
    isActive: false,
    deploymentEnv: "Staging",
    budgetStatus: "close"
  },
  {
    llmConnectionId: 3,
    llmConnectionName: "Azure OpenAI Service",
    datasetVersion: "v2.0.3",
    platform: "Microsoft Azure",
    model: true,
    isActive: true,
    deploymentEnv: "Production",
    budgetStatus: "over"
  },
  {
    llmConnectionId: "conn-4",
    llmConnectionName: "Local Llama 2 Model",
    datasetVersion: "v1.5.2",
    platform: "Local",
    model: false,
    isActive: true,
    deploymentEnv: "Development",
    budgetStatus: "within"
  },
  {
    llmConnectionId: 5,
    llmConnectionName: "Google PaLM API",
    datasetVersion: "v1.9.1",
    platform: "Google Cloud",
    model: true,
    isActive: false,
    deploymentEnv: "Testing",
    budgetStatus: "within"
  },
  {
    llmConnectionId: 6,
    llmConnectionName: "Cohere Command Model",
    datasetVersion: "v2.2.0",
    platform: "Cohere",
    model: true,
    isActive: true,
    deploymentEnv: "Production",
    budgetStatus: "close"
  },
  {
    llmConnectionId: "conn-7",
    llmConnectionName: "Hugging Face Transformers",
    datasetVersion: "v1.7.8",
    platform: "Hugging Face",
    model: false,
    isActive: false,
    deploymentEnv: "Development",
    budgetStatus: "within"
  },
  {
    llmConnectionId: 8,
    llmConnectionName: "AWS Bedrock Claude",
    datasetVersion: "v2.0.7",
    platform: "AWS Bedrock",
    model: true,
    isActive: true,
    deploymentEnv: "Production",
    budgetStatus: "over"
  }
];

// Example usage with a single connection
export const singleMockConnection: LLMConnectionData = {
  llmConnectionId: "demo-1",
  llmConnectionName: "Demo LLM Connection",
  datasetVersion: "v1.0.0",
  platform: "Demo Platform",
  model: true,
  isActive: true,
  deploymentEnv: "Demo",
  budgetStatus: "within"
};

// Helper function to get detailed connection data for forms
export const getDetailedConnectionData = (connectionId: string | number) => {
  const connection = mockLLMConnections.find(
    conn => conn.llmConnectionId.toString() === connectionId.toString()
  );

  if (!connection) return null;

  // Map basic connection data to detailed form data
  const detailedData: Record<string | number, any> = {
    1: {
      llmPlatform: "openai",
      llmModel: "gpt-4",
      embeddingModelPlatform: "openai",
      embeddingModel: "text-embedding-3-large",
      llmApiKey: "sk-***************************",
      embeddingApiKey: "sk-***************************",
      monthlyBudget: "500",
      deploymentEnvironment: "production"
    },
    2: {
      llmPlatform: "anthropic",
      llmModel: "claude-3-sonnet",
      embeddingModelPlatform: "cohere",
      embeddingModel: "embed-english-v3.0",
      llmApiKey: "sk-ant-*********************",
      embeddingApiKey: "***************************",
      monthlyBudget: "300",
      deploymentEnvironment: "testing"
    },
    3: {
      llmPlatform: "azure",
      llmModel: "gpt-4-turbo",
      embeddingModelPlatform: "azure",
      embeddingModel: "text-embedding-ada-002",
      llmApiKey: "***************************",
      embeddingApiKey: "***************************",
      monthlyBudget: "800",
      deploymentEnvironment: "production"
    },
    "conn-4": {
      llmPlatform: "local",
      llmModel: "custom",
      embeddingModelPlatform: "local",
      embeddingModel: "custom",
      llmApiKey: "local-api-key",
      embeddingApiKey: "local-embedding-key",
      monthlyBudget: "0",
      deploymentEnvironment: "testing"
    },
    5: {
      llmPlatform: "google",
      llmModel: "palm-2",
      embeddingModelPlatform: "google",
      embeddingModel: "textembedding-gecko",
      llmApiKey: "AIza***************************",
      embeddingApiKey: "AIza***************************",
      monthlyBudget: "400",
      deploymentEnvironment: "testing"
    },
    6: {
      llmPlatform: "cohere",
      llmModel: "command",
      embeddingModelPlatform: "cohere",
      embeddingModel: "embed-english-v3.0",
      llmApiKey: "***************************",
      embeddingApiKey: "***************************",
      monthlyBudget: "250",
      deploymentEnvironment: "production"
    },
    "conn-7": {
      llmPlatform: "huggingface",
      llmModel: "custom-transformers",
      embeddingModelPlatform: "huggingface",
      embeddingModel: "sentence-transformers",
      llmApiKey: "hf_***************************",
      embeddingApiKey: "hf_***************************",
      monthlyBudget: "100",
      deploymentEnvironment: "development"
    },
    8: {
      llmPlatform: "aws",
      llmModel: "claude-3-sonnet",
      embeddingModelPlatform: "aws",
      embeddingModel: "titan-embed-text-v1",
      llmApiKey: "AKIA***************************",
      embeddingApiKey: "AKIA***************************",
      monthlyBudget: "600",
      deploymentEnvironment: "production"
    }
  };

  return detailedData[connectionId] || {
    llmPlatform: "",
    llmModel: "",
    embeddingModelPlatform: "",
    embeddingModel: "",
    llmApiKey: "",
    embeddingApiKey: "",
    monthlyBudget: "",
    deploymentEnvironment: "testing"
  };
};
