import { FC, PropsWithChildren, useState } from 'react';
import Button from 'components/Button';
import Label from 'components/Label';
import { useDialog } from 'hooks/useDialog';
import './LLMConnectionCard.scss';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Switch } from 'components/FormElements';
import { updateLLMConnectionStatus } from 'services/llmConnections';
import { useToast } from 'hooks/useToast';
import { ToastTypes } from 'enums/commonEnums';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { llmConnectionsQueryKeys } from 'utils/queryKeys';
import { AxiosError } from 'axios';

type LLMConnectionCardProps = {
  llmConnectionId: number | string;
  llmConnectionName?: string;
  platform?: string;
  model?: string;
  isActive?: boolean;
  deploymentEnv?: string;
  budgetStatus?: string;
  onStatusChange?: (id: number | string, newStatus: boolean) => void;
};

const LLMConnectionCard: FC<PropsWithChildren<LLMConnectionCardProps>> = ({
  llmConnectionId,
  llmConnectionName,
  platform,
  model,
  isActive,
  deploymentEnv,
  budgetStatus,
  onStatusChange,
}) => {
  const { open, close } = useDialog();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();

  const updateStatusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string | number; status: 'active' | 'inactive' }) =>
      updateLLMConnectionStatus(id, status),
    onSuccess: async (data, variables) => {
      // Invalidate queries to refresh the data
      await queryClient.invalidateQueries({
        queryKey: llmConnectionsQueryKeys.all()
      });
      
      toast.open({
        type: ToastTypes.SUCCESS,
        title: t('toast.success.title'),
        message: `Connection ${variables.status === 'active' ? 'activated' : 'deactivated'} successfully`,
      });
      
      // Call the parent callback to update the list immediately
      if (onStatusChange) {
        onStatusChange(llmConnectionId, variables.status === 'active');
      }
    },
    onError: (error: AxiosError) => {
      console.error('Error updating connection status:', error);
      toast.open({
        type: ToastTypes.ERROR,
        title: t('toast.error.title'),
        message: 'Failed to update connection status',
      });
    },
  });

  const handleStatusChange = async (checked: boolean) => {
    if (updateStatusMutation.isLoading) return;
    
    const newStatus = checked ? 'active' : 'inactive';
    updateStatusMutation.mutate({
      id: llmConnectionId,
      status: newStatus
    });
  };


  const renderDeploymentEnv = (deploymentEnvironment: string | undefined) => {
    if (deploymentEnvironment === "testing") {
      return (
        <Label type="info">
          {t('dataModels.environments.testing')}
        </Label>
      );
    } else if (deploymentEnvironment === "production") {
      return (
        <Label type="success">
          {t('dataModels.environments.production')}
        </Label>
      );
    }
  };

  const renderBudgetStatus = (status: string | undefined) => {
    if (status === "within_budget") {
      return (
        <Label type="success">
          {t('dataModels.budgetStatus.withinBudget')}
        </Label>
      );
    } else if (status === "over_budget") {
      return (
        <Label type="error">
          {t('dataModels.budgetStatus.overBudget')}
        </Label>
      );
    } else if (status === "close_to_exceed") {
      return (
        <Label type="warning">
          {t('dataModels.budgetStatus.closeToExceed')}
        </Label>
      );
    }
  };

  return (
    <div>
      <div className="dataset-group-card">
        <div className="flex space-between">
          <p>{llmConnectionName}</p>
          <Switch
            label=""
            checked={isActive ?? false}
            onCheckedChange={handleStatusChange}
            disabled={updateStatusMutation.isLoading}
          />
        </div>

        <div className="flex" style={{ flexWrap: 'wrap', gap: '5px' }}>
          <div className="label-row">
            <span className="label-title">
              {t('dataModels.filters.platform')}:
            </span>
            <span className="label-value">{platform ?? 'N/A'}</span>
          </div>
          <div className="label-row">
            <span className="label-title">
              {t('dataModels.filters.model')}:
            </span>
            <span className="label-value">{model ?? 'N/A'}</span>
          </div>
          <div className='label-row'>
            {renderDeploymentEnv(deploymentEnv)}
            {renderBudgetStatus(budgetStatus)}
          </div>
        </div>
        <div className="button-row mt-3">
          <Button
            appearance="secondary"
            size="s"
            onClick={() => navigate(`/view-llm-connection?id=${llmConnectionId}`)}
          >
            {t('dataModels.settings') ?? ''}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default LLMConnectionCard;