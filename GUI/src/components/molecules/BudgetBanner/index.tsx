import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { checkBudgetStatus, BudgetStatus } from 'services/llmConnections';
import { llmConnectionsQueryKeys } from 'utils/queryKeys';
import './BudgetBanner.scss';
import Button from 'components/Button';
import { MdOutlineGppMaybe, MdWarning } from 'react-icons/md';

const BudgetBanner: React.FC = () => {
    const { t } = useTranslation();
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
        const platformKey = data?.llmPlatform === "aws" ? "aws" : "azure";
        const platformName = t(`budgetBanner.platforms.${platformKey}`);

        if (exceeded_stop_budget) {
            return {
                type: 'error' as const,
                message: t('budgetBanner.productionDisabled'),
                description: t('budgetBanner.budgetExceededDescription', { platform: platformName }),
                icon: <MdOutlineGppMaybe size={30} />
            };
        }

        if (exceeded_warn_budget) {
            return {
                type: 'warning' as const,
                message: t('budgetBanner.budgetUsageMessage', { percentage: used_budget_percentage?.toFixed(1) }),
                description: t('budgetBanner.budgetUsageDescription', { 
                    platform: platformName, 
                    percentage: used_budget_percentage?.toFixed(1) 
                }),
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
                        {t('budgetBanner.reviewBudgetButton')}
                    </Button>
                ) : (
                    <Button size='s' onClick={() => navigate(`/view-llm-connection?id=${budgetStatus.data.id}`)}>
                        {t('budgetBanner.updateBudgetButton')}
                    </Button>
                )
            }
        </div>
    );
};

export default BudgetBanner;
