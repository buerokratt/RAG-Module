import { FC, PropsWithChildren } from 'react';
import Button from 'components/Button';
import Label from 'components/Label';
import { useDialog } from 'hooks/useDialog';
import './LLMConnectionCard.scss';
import { useTranslation } from 'react-i18next';
import { formatDate } from 'utils/commonUtilts';
import { useNavigate } from 'react-router-dom';
import { pl } from 'date-fns/locale';
import { Switch } from 'components/FormElements';

type LLMConnectionCardProps = {
  llmConnectionId: number | string;
  llmConnectionName?: string;
  platform?: string;
  model?: string;
  isActive?: boolean;
  deploymentEnv?: string;
  budgetStatus?: string;
};

const LLMConnectionCard: FC<PropsWithChildren<LLMConnectionCardProps>> = ({
  llmConnectionId,
  llmConnectionName,
  platform,
  model,
  isActive,
  deploymentEnv,
  budgetStatus,

}) => {
  const { open, close } = useDialog();
  const { t } = useTranslation();
  const navigate = useNavigate();


  const renderDeploymentEnv = (deploymentEnvironment: string | undefined) => {
    return (
        <Label type="success">
          {deploymentEnvironment}
        </Label>
      );
  };

  const renderBudgetStatus = (status: string | undefined) => {
    if (status === "within_budget") {
      return (
        <Label type="success">
          {'Within Budget'}
        </Label>
      );
    } else if (status === "over_budget") {
      return (
        <Label type="error">
          {'Over Budget'}
        </Label>
      );
    } else if (status === "close_to_exceed") {
      return (
        <Label type="warning">
          {'Close to Exceed Budget'}
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
            checked={false}
            onCheckedChange={() => {}}
          />
        </div>

        <div className="flex" style={{ flexWrap: 'wrap', gap: '5px' }}>
          <div className="label-row">
            <span className="label-title">
              {'Platform'}:
            </span>
            <span className="label-value">{platform ?? 'N/A'}</span>
          </div>
          <div className="label-row">
            <span className="label-title">
              {'Model'}:
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
            {t('datasets.datasetCard.settings') ?? ''}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default LLMConnectionCard;