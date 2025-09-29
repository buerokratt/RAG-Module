import React from 'react';
import { useForm, Controller } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import FormInput from 'components/FormElements/FormInput';
import FormSelect from 'components/FormElements/FormSelect';
import Button from 'components/Button';
import Track from 'components/Track';
import './LLMConnectionForm.scss';

export type LLMConnectionFormData = {
  llmPlatform: string;
  llmModel: string;
  embeddingModelPlatform: string;
  embeddingModel: string;
  llmApiKey: string;
  embeddingApiKey: string;
  monthlyBudget: string;
  deploymentEnvironment: string;
  // AWS Bedrock specific fields
  accessKey?: string;
  secretKey?: string;
  // Azure specific fields
  deploymentName?: string;
  endpoint?: string;
  azureApiKey?: string;
};

type LLMConnectionFormProps = {
  onSubmit: (data: LLMConnectionFormData) => void;
  onCancel: () => void;
  onDelete: () => void;
  defaultValues?: Partial<LLMConnectionFormData>;
  isEditing?: boolean;
  readOnly?: boolean;
};

const LLMConnectionForm: React.FC<LLMConnectionFormProps> = ({
  onSubmit,
  onCancel,
  onDelete,
  defaultValues,
  isEditing = false,
  readOnly = false,
}) => {
  const { t } = useTranslation();
  const {
    control,
    handleSubmit,
    watch,
    formState: { errors, isDirty, isValid },
  } = useForm<LLMConnectionFormData>({
    defaultValues: {
      llmPlatform: '',
      llmModel: '',
      embeddingModelPlatform: '',
      embeddingModel: '',
      llmApiKey: '',
      embeddingApiKey: '',
      monthlyBudget: '',
      deploymentEnvironment: 'development',
      // AWS Bedrock specific fields
      accessKey: '',
      secretKey: '',
      // Azure specific fields
      deploymentName: '',
      endpoint: '',
      azureApiKey: '',
      ...defaultValues,
    },
    mode: 'onChange',
  });

  const selectedLLMPlatform = watch('llmPlatform');
  const selectedEmbeddingPlatform = watch('embeddingModelPlatform');

  // Platform options
  const llmPlatformOptions = [
    { label: 'Azure OpenAI', value: 'azure' },
    { label: 'AWS Bedrock', value: 'bedrock' },
    { label: 'Hugging Face', value: 'huggingface' },
  ];

  const embeddingPlatformOptions = [
    { label: 'OpenAI', value: 'openai' },
    { label: 'Hugging Face', value: 'huggingface' },
    { label: 'Azure OpenAI', value: 'azure' },
  ];

  // Model options based on selected platform
  const getLLMModelOptions = (platform: string) => {
    switch (platform) {
      case 'azure':
        return [
          { label: 'GPT-4', value: 'gpt-4' },
          { label: 'GPT-4 Turbo', value: 'gpt-4-turbo' },
          { label: 'GPT-3.5 Turbo', value: 'gpt-3.5-turbo' },
          { label: 'GPT-4o', value: 'gpt-4o' },
        ];
      case 'bedrock':
        return [
          { label: 'Claude 3 Sonnet', value: 'anthropic.claude-3-sonnet-20240229-v1:0' },
          { label: 'Claude 3 Haiku', value: 'anthropic.claude-3-haiku-20240307-v1:0' },
          { label: 'Claude 3 Opus', value: 'anthropic.claude-3-opus-20240229-v1:0' },
          { label: 'Titan Text G1 - Express', value: 'amazon.titan-text-express-v1' },
          { label: 'Llama 2 70B Chat', value: 'meta.llama2-70b-chat-v1' },
        ];
      case 'huggingface':
        return [
          { label: 'Llama 2 7B Chat', value: 'meta-llama/Llama-2-7b-chat-hf' },
          { label: 'Llama 2 13B Chat', value: 'meta-llama/Llama-2-13b-chat-hf' },
          { label: 'Mistral 7B Instruct', value: 'mistralai/Mistral-7B-Instruct-v0.1' },
          { label: 'CodeLlama 7B Instruct', value: 'codellama/CodeLlama-7b-Instruct-hf' },
        ];
      default:
        return [{ label: 'Custom Model', value: 'custom' }];
    }
  };

  const getEmbeddingModelOptions = (platform: string) => {
    switch (platform) {
      case 'openai':
        return [
          { label: 'text-embedding-ada-002', value: 'text-embedding-ada-002' },
          { label: 'text-embedding-3-small', value: 'text-embedding-3-small' },
          { label: 'text-embedding-3-large', value: 'text-embedding-3-large' },
        ];
      case 'azure':
        return [
          { label: 'text-embedding-ada-002', value: 'text-embedding-ada-002' },
          { label: 'text-embedding-3-small', value: 'text-embedding-3-small' },
          { label: 'text-embedding-3-large', value: 'text-embedding-3-large' },
        ];
      case 'huggingface':
        return [
          { label: 'all-MiniLM-L6-v2', value: 'sentence-transformers/all-MiniLM-L6-v2' },
          { label: 'all-mpnet-base-v2', value: 'sentence-transformers/all-mpnet-base-v2' },
          { label: 'all-distilroberta-v1', value: 'sentence-transformers/all-distilroberta-v1' },
        ];
      default:
        return [{ label: 'Custom Model', value: 'custom' }];
    }
  };

  const deploymentEnvironments = [
    { label: 'Testing', value: 'testing' },
    { label: 'Production', value: 'production' },
  ];

  const renderPlatformSpecificFields = () => {
    switch (selectedLLMPlatform) {
      case 'bedrock':
        return (
          <>
            <div className="form-row">
              <p className='form-label'>Access Key</p>
              <p className='form-description'>AWS Access Key for Bedrock service</p>
              <Controller
                name="accessKey"
                control={control}
                rules={{ required: 'Access Key is required for AWS Bedrock' }}
                render={({ field }) => (
                  <FormInput
                    label=""
                    type="password"
                    placeholder="Enter AWS Access Key"
                    error={errors.accessKey?.message}
                    {...field}
                  />
                )}
              />
            </div>
            <div className="form-row">
              <p className='form-label'>Secret Key</p>
              <p className='form-description'>AWS Secret Key for Bedrock service</p>
              <Controller
                name="secretKey"
                control={control}
                rules={{ required: 'Secret Key is required for AWS Bedrock' }}
                render={({ field }) => (
                  <FormInput
                    label=""
                    type="password"
                    placeholder="Enter AWS Secret Key"
                    error={errors.secretKey?.message}
                    {...field}
                  />
                )}
              />
            </div>
          </>
        );
      case 'azure':
        return (
          <>
            <div className="form-row">
              <p className='form-label'>Deployment Name</p>
              <p className='form-description'>Azure OpenAI deployment name</p>
              <Controller
                name="deploymentName"
                control={control}
                rules={{ required: 'Deployment Name is required for Azure OpenAI' }}
                render={({ field }) => (
                  <FormInput
                    label=""
                    placeholder="Enter deployment name"
                    error={errors.deploymentName?.message}
                    {...field}
                  />
                )}
              />
            </div>
            <div className="form-row">
              <p className='form-label'>Endpoint / Target URI</p>
              <p className='form-description'>Azure OpenAI service endpoint URL</p>
              <Controller
                name="endpoint"
                control={control}
                rules={{ 
                  required: 'Endpoint is required for Azure OpenAI',
                  pattern: {
                    value: /^https?:\/\/.+/,
                    message: 'Please enter a valid URL starting with http:// or https://'
                  }
                }}
                render={({ field }) => (
                  <FormInput
                    label=""
                    placeholder="https://your-resource.openai.azure.com/"
                    error={errors.endpoint?.message}
                    {...field}
                  />
                )}
              />
            </div>
            <div className="form-row">
              <p className='form-label'>API Key</p>
              <p className='form-description'>Azure OpenAI API key</p>
              <Controller
                name="azureApiKey"
                control={control}
                rules={{ required: 'API Key is required for Azure OpenAI' }}
                render={({ field }) => (
                  <FormInput
                    label=""
                    type="password"
                    placeholder="Enter Azure OpenAI API key"
                    error={errors.azureApiKey?.message}
                    {...field}
                  />
                )}
              />
            </div>
          </>
        );
      case 'huggingface':
        return (
          <div className="form-row">
            <p className='form-label'>LLM API Key</p>
            <p className='form-description'>Hugging Face API token for model access</p>
            <Controller
              name="llmApiKey"
              control={control}
              rules={{ required: 'API Key is required for Hugging Face' }}
              render={({ field }) => (
                <FormInput
                  label=""
                  type="password"
                  placeholder="Enter Hugging Face API token"
                  error={errors.llmApiKey?.message}
                  {...field}
                />
              )}
            />
          </div>
        );
      default:
        return (
          <div className="form-row">
            <p className='form-label'>LLM API Key</p>
            <p className='form-description'>The API key of the LLM model</p>
            <Controller
              name="llmApiKey"
              control={control}
              rules={{ required: 'LLM API Key is required' }}
              render={({ field }) => (
                <FormInput
                  label=""
                  type="password"
                  placeholder="Enter your LLM API key"
                  error={errors.llmApiKey?.message}
                  {...field}
                />
              )}
            />
          </div>
        );
    }
  };

  const handleFormSubmit = (data: LLMConnectionFormData) => {
    const cleanedData = {
      ...data,
      monthlyBudget: data.monthlyBudget.replace(/,/g, ''),
    };
    onSubmit(cleanedData);
  };

  return (
    <div className="llm-connection-form">
      <form onSubmit={handleSubmit(handleFormSubmit)}>
        <div className="form-section">
          <h3 className="form-section-title">LLM Configuration</h3>

          <div className="form-row">
            <p className='form-label'>LLM Platform</p>
            <p className='form-description'> Cloud / local platform in which your model is hosted</p>
            <Controller
              name="llmPlatform"
              control={control}
              rules={{ required: 'LLM Platform is required' }}
              render={({ field }) => (
                <FormSelect
                  label=""
                  options={llmPlatformOptions}
                  placeholder="Select LLM Platform"
                  error={errors.llmPlatform?.message}
                  disabled={readOnly}
                  onSelectionChange={(selected) => {
                    field.onChange(selected?.value || '');
                  }}
                  defaultValue={field.value}
                  {...field}
                />
              )}
            />
          </div>

          <div className="form-row">
            <p className='form-label'>LLM Model</p>
            <p className='form-description'>The LLM model that you want to use</p>

            <Controller
              name="llmModel"
              control={control}
              rules={{ required: 'LLM Model is required' }}
              render={({ field }) => (
                <FormSelect
                  label=""
                  options={getLLMModelOptions(selectedLLMPlatform)}
                  placeholder="Select LLM Model"
                  error={errors.llmModel?.message}
                  disabled={!selectedLLMPlatform || readOnly}
                  onSelectionChange={(selected) => {
                    field.onChange(selected?.value || '');
                  }}
                  defaultValue={field.value}
                  {...field}
                />
              )}
            />
          </div>

          {/* Platform-specific fields */}
          {renderPlatformSpecificFields()}
        </div>

        <div className="form-section">
          <h3 className="form-section-title">Embedding Model Configuration</h3>

          <div className="form-row">
            <p className='form-label'>Embedding Model Platform</p>
            <p className='form-description'>This is the cloud / local platform in which your embedding model is hosted</p>

            <Controller
              name="embeddingModelPlatform"
              control={control}
              rules={{ required: 'Embedding Model Platform is required' }}
              render={({ field }) => (
                <FormSelect
                  label=""
                  options={embeddingPlatformOptions}
                  placeholder="Select Embedding Platform"
                  error={errors.embeddingModelPlatform?.message}
                  onSelectionChange={(selected) => {
                    field.onChange(selected?.value || '');
                  }}
                  defaultValue={field.value}
                  {...field}
                />
              )}
            />
          </div>

          <div className="form-row">
            <p className='form-label'>Embedding Model</p>
            <p className='form-description'>The embedding model that will be used for searching your knowledge base</p>

            <Controller
              name="embeddingModel"
              control={control}
              rules={{ required: 'Embedding Model is required' }}
              render={({ field }) => (
                <FormSelect
                  label=""
                  options={getEmbeddingModelOptions(selectedEmbeddingPlatform)}
                  placeholder="Select Embedding Model"
                  error={errors.embeddingModel?.message}
                  disabled={!selectedEmbeddingPlatform}
                  onSelectionChange={(selected) => {
                    field.onChange(selected?.value || '');
                  }}
                  defaultValue={field.value}
                  {...field}
                />
              )}
            />
          </div>

          <div className="form-row">
            <p className='form-label'>Embedding Model API Key</p>
            <p className='form-description'>API key of your embedding model</p>

            <Controller
              name="embeddingApiKey"
              control={control}
              rules={{ required: 'Embedding API Key is required' }}
              render={({ field }) => (
                <FormInput
                  label=""
                  type="password"
                  placeholder="Enter your Embedding API key"
                  error={errors.embeddingApiKey?.message}
                  {...field}
                />
              )}
            />
          </div>
        </div>

        <div className="form-section">
          <h3 className="form-section-title">Budget & Deployment</h3>

          <div className="form-row">
            <p className='form-label'>Monthly Budget</p>
            <p className='form-description'>Total monthly budget including embedding model and LLM model. If the LLM integration usage cost exceeds the below
              budget, the LLM will respond with an “inactive” status</p>

            <Controller
              name="monthlyBudget"
              control={control}
              rules={{
                required: 'Monthly Budget is required',
                pattern: {
                  value: /^[\d,]+(\.\d{1,2})?$/,
                  message: 'Please enter a valid budget amount'
                },
                validate: value => {
                  const numericValue = value.replace(/,/g, '');
                  return Number(numericValue) > 0 || 'Monthly Budget must be a positive number';
                }
              }}
              render={({ field }) => (
                <FormInput
                  label=""
                  placeholder="Enter monthly budget"
                  error={errors.monthlyBudget?.message}
                  {...field}
                  prefix='€'
                  formatAsNumber={true}
                />
              )}
            />
          </div>

          <div className="form-row">
            <Controller
              name="deploymentEnvironment"
              control={control}
              rules={{ required: 'Deployment Environment is required' }}
              render={({ field }) => (
                <div className="radio-group">
                  <label className="radio-group-label">Deployment Environment</label>
                  <div className="radio-options">
                    {deploymentEnvironments.map((env) => (
                      <label key={env.value} className="radio-option">
                        <input
                          type="radio"
                          value={env.value}
                          checked={field.value === env.value}
                          onChange={(e) => field.onChange(e.target.value)}
                          className="radio-input"
                        />
                        <span className="radio-label">{env.label}</span>
                      </label>
                    ))}
                  </div>
                  {errors.deploymentEnvironment && (
                    <p className="input__inline_error">{errors.deploymentEnvironment.message}</p>
                  )}
                </div>
              )}
            />
          </div>
          <Track className="form-footer" gap={16} justify="end">
            <div className="flex-grid">
              <Button
                appearance="secondary"
                onClick={onCancel}
                type="button"
              >
                {t('global.cancel') || 'Cancel'}
              </Button>
              {isEditing && (<Button
                appearance="error"
                onClick={onDelete}
              >
                Delete Connection
              </Button>)}
              <Button
                type="submit"
                disabled={!isDirty || !isValid}
                appearance="primary"
              >
                {isEditing ? ('Update Connection') : ('Create Connection')}
              </Button>
            </div>
          </Track>
        </div>

      </form>
    </div>
  );
};

export default LLMConnectionForm;
