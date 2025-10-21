import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { checkBudgetStatus, BudgetStatus } from 'services/llmConnections';
import { llmConnectionsQueryKeys } from 'utils/queryKeys';
import './BudgetBanner.scss';
import Button from 'components/Button';
import { MdOutlineGppMaybe, MdWarning } from 'react-icons/md';

const BudgetBanner: React.FC = () => {
    const navigate = useNavigate();
    const { data: budgetStatus } = useQuery({
        queryKey: llmConnectionsQueryKeys.budgetStatus(),
        queryFn: checkBudgetStatus,
    });

    if (!budgetStatus) {
        return null;
    }

    const getBannerContent = (status: BudgetStatus) => {
        const { used_budget_percentage, exceeded_stop_budget, exceeded_warn_budget, data } = status;

        if (exceeded_stop_budget) {
            return {
                type: 'error' as const,
                message: `Production LLM connection disabled`,
                description: `${data?.llmPlatform === "aws" ? "AWS Bedrock" : "Azure OpenAI"} integration has exceeded its budget. Update budget to reactivate LLM connection.`,
                icon: <MdOutlineGppMaybe size={30} />
            };
        }

        if (exceeded_warn_budget) {
            return {
                type: 'warning' as const,
                message: `${used_budget_percentage?.toFixed(1)}% of connection budget is used.`,
                description: `${data?.llmPlatform === "aws" ? "AWS Bedrock" : "Azure OpenAI"} integration has used ${used_budget_percentage?.toFixed(1)}% of its budget. Review connection budget to avoid disconnections`,
                icon: <MdWarning size={30} />

            };
        }

        return null; // Don't show banner if within budget
    };

    const bannerContent = getBannerContent(budgetStatus);

    if (!bannerContent) {
        return null;
    }

    return (
        <div className={`budget-banner budget-banner--${bannerContent.type}`}>
            <div className='budget-banner__content'>
                {bannerContent.icon}
                <span className="budget-banner__message">
                    {bannerContent.message}
                </span>
            </div>
            <span className="budget-banner__description">
                {bannerContent.description}
            </span>
            <br></br>
            <div className='m-3'></div>
            {budgetStatus.exceeded_warn_budget && !budgetStatus.exceeded_stop_budget ?
                (
                    <Button size='s' onClick={() => navigate(`/view-llm-connection?id=${budgetStatus.data.id}`)}>
                        Review Budget
                    </Button>
                ) : (
                    <Button size='s' onClick={() => navigate(`/view-llm-connection?id=${budgetStatus.data.id}`)}>
                        Update Budget
                    </Button>
                )
            }
        </div>
    );
};

export default BudgetBanner;
