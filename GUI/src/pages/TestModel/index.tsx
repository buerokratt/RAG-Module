import { useMutation, useQuery } from '@tanstack/react-query';
import { Button, FormSelect, FormTextarea } from 'components';
import CircularSpinner from 'components/molecules/CircularSpinner/CircularSpinner';
import { FC, useState } from 'react';
import { useTranslation } from 'react-i18next';
import './TestLLM.scss';
import { useDialog } from 'hooks/useDialog';
import { fetchLLMConnectionsPaginated, LegacyLLMConnectionFilters } from 'services/llmConnections';
import { viewInferenceResult, InferenceRequest, InferenceResponse } from 'services/inference';
import { llmConnectionsQueryKeys } from 'utils/queryKeys';
import { ButtonAppearanceTypes } from 'enums/commonEnums';

const TestLLM: FC = () => {
  const { t } = useTranslation();
  const { open: openDialog, close: closeDialog } = useDialog();
  const [inferenceResult, setInferenceResult] = useState<InferenceResponse['response'] | null>(null);
  const [testLLM, setTestLLM] = useState({
    connectionId: null,
    text: '',
  });

  // Fetch LLM connections for dropdown - using the working legacy endpoint for now
  const { data: connections, isLoading: isLoadingConnections } = useQuery({
    queryKey: llmConnectionsQueryKeys.list({
      page: 1,
      pageSize: 100, // Get all connections for dropdown
      sorting: 'created_at desc',
    }),
    queryFn: () => fetchLLMConnectionsPaginated({
      pageNumber: 1,
      pageSize: 100,
      sortBy: 'created_at desc',
    }),
  });

  // Transform connections data for dropdown
  const connectionOptions = connections?.map((connection: any) => ({
    label: `${connection.llmPlatform} - ${connection.llmModel} (${connection.environment})`,
    value: connection.id,
  })) || [];

  // Inference mutation
  const inferenceMutation = useMutation({
    mutationFn: (request: InferenceRequest) => viewInferenceResult(request),
    onSuccess: (data: InferenceResponse) => {
      setInferenceResult(data?.response);
    },
    onError: (error: any) => {
      console.error('Error getting inference result:', error);
      openDialog({
        title: 'Inference Error',
        content: <p>Failed to get inference result. Please try again.</p>,
        footer: (
          <Button
            appearance={ButtonAppearanceTypes.PRIMARY}
            onClick={closeDialog}
          >
            Close
          </Button>
        ),
      });
    },
  });

  const handleSend = () => {
    if (testLLM.connectionId && testLLM.text) {
      inferenceMutation.mutate({
        llmConnectionId: Number(testLLM.connectionId),
        message: testLLM.text,
      });
    }
  };

  const handleChange = (key: string, value: string | number) => {
    setTestLLM((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  return (
    <div>
      {isLoadingConnections ? (
        <CircularSpinner />
      ) : (
        <div className="container">
          <div className="title_container">
            <div className="title">{'Test LLM'}</div>
          </div>
          <div className="llm-connection-section">
            <p>{"LLM Connection"}</p>
            <div className="llm-connection-controls">

              <FormSelect
                label=""
                name="connectionId"
                options={connectionOptions}
                placeholder={'-Select LLM Connection-'}
                onSelectionChange={(selection) => {
                  handleChange('connectionId', selection?.value as string);
                }}
                value={testLLM?.connectionId === null ? 'Connection does not exist' : undefined} 
                defaultValue={testLLM?.connectionId ?? undefined}
              />
            </div>
          </div>

          <div className="testModalFormTextArea">
            <p>{t('testModels.classifyTextLabel')}</p>
            <FormTextarea
              label=""
              name=""
              maxLength={1000}
              onChange={(e) => handleChange('text', e.target.value)}
              showMaxLength={true}
            />
          </div>
          <div className="testModalClassifyButton">
            <Button
              onClick={handleSend}
              disabled={!testLLM.connectionId || !testLLM.text || inferenceMutation.isLoading}
            >
              {inferenceMutation.isLoading ? 'Sending...' : 'Send'}
            </Button>
          </div>

          {/* Inference Result */}

          {inferenceResult && (
            <div className="inference-results-container">
            <div className="result-item">
              <strong>Chat ID:</strong> {inferenceResult.chatId}
            </div>
            <div className="result-item">
              <strong>LLM Service Active:</strong> {inferenceResult.llmServiceActive ? 'Yes' : 'No'}
            </div>
            <div className="result-item">
              <strong>Question Out of LLM Scope:</strong> {inferenceResult.questionOutOfLlmScope ? 'Yes' : 'No'}
            </div>
            <div className="result-item">
              <strong>Response:</strong>
              <div className="response-content">
                {inferenceResult.content}
              </div>
            </div>
          </div>
          )}

          {/* Error State */}
          {inferenceMutation.isError && (
            <div className="classification-error">
              <p>{t('testModels.classificationFailed') || 'Inference failed. Please try again.'}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default TestLLM;