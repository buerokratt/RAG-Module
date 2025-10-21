import { FC, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, FormSelect } from 'components';
import Pagination from 'components/molecules/Pagination';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { formattedArray } from 'utils/commonUtils';
import DataModelCard from 'components/molecules/LLMConnectionCard';
import CircularSpinner from 'components/molecules/CircularSpinner/CircularSpinner';
import { ButtonAppearanceTypes } from 'enums/commonEnums';
import NoDataView from 'components/molecules/NoDataView';
import BudgetBanner from 'components/molecules/BudgetBanner';
import './LLMConnections.scss';
import { platforms, trainingStatuses } from 'config/dataModelsConfig';
import LLMConnectionCard from 'components/molecules/LLMConnectionCard';
import { fetchLLMConnectionsPaginated, LLMConnectionFilters, LLMConnection, getProductionConnection } from 'services/llmConnections';
import { llmConnectionsQueryKeys } from 'utils/queryKeys';

const LLMConnections: FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [pageIndex, setPageIndex] = useState<number>(1);
  const [filters, setFilters] = useState<LLMConnectionFilters>({
    pageNumber: 1,
    pageSize: 10,
    sortBy: 'created_at',
    sortOrder: 'desc',
  });

  // Fetch LLM connections using TanStack Query with new paginated endpoint
  const { data: connectionsResponse, isLoading: isModelDataLoading, error } = useQuery({
    queryKey: llmConnectionsQueryKeys.paginatedList(filters),
    queryFn: () => fetchLLMConnectionsPaginated(filters),
  });

  // Fetch production connection separately
  const { data: productionConnection, isLoading: isProductionLoading } = useQuery({
    queryKey: llmConnectionsQueryKeys.production(),
    queryFn: getProductionConnection,
  });


  const llmConnections = connectionsResponse;
  const totalPages = connectionsResponse?.[0]?.totalPages || 1;

  // Update filters when pageIndex changes
  useEffect(() => {
    setFilters(prev => ({ ...prev, pageNumber: pageIndex }));
  }, [pageIndex]);

  const handleFilterChange = (
    name: string,
    value: string | number | undefined | { name: string; id: string }
  ) => {
    let filterUpdate: Partial<LLMConnectionFilters> = {};

    if (name === 'sorting') {
      // Handle sorting format - no conversion needed, use snake_case directly
      const sortingValue = value as string;
      const [sortBy, sortOrder] = sortingValue.split(' ');

      filterUpdate = {
        sortBy: sortBy,
        sortOrder: sortOrder as 'asc' | 'desc'
      };
    } else {
      filterUpdate = { [name]: value };
    }

    setFilters((prevFilters) => ({
      ...prevFilters,
      ...filterUpdate,
    }));

    // Reset to first page when filters change
    if (name !== 'pageNumber') {
      setPageIndex(1);
    }
  };

  // Platform filter options
  const platformOptions = [
    { label: 'All Platforms', value: 'all' },
    { label: 'Azure OpenAI', value: 'azure' },
    { label: 'AWS Bedrock', value: 'aws' },
  ];

  // LLM Model filter options - these would ideally come from an API
  const llmModelOptions = [
    { label: 'All Models', value: 'all' },
    { label: 'GPT-4 Mini', value: 'gpt-4o-mini' },
    { label: 'GPT-4o', value: 'gpt-4o' },
    { label: 'Anthropic Claude 3.5 Sonnet', value: 'anthropic-claude-3.5-sonnet' },
    { label: 'Anthropic Claude 3.7 Sonnet', value: 'anthropic-claude-3.7-sonnet' },
  ];

  // Environment filter options
  const environmentOptions = [
    { label: 'All Environments', value: 'all' },
    { label: 'Testing', value: 'testing' },
    { label: 'Production', value: 'production' },
  ];

  // Sort options - using snake_case format for backend
  const sortOptions = [
    { label: 'Created Date (Newest)', value: 'created_at desc' },
    { label: 'Created Date (Oldest)', value: 'created_at asc' },
    { label: 'Platform A-Z', value: 'llm_platform asc' },
    { label: 'Platform Z-A', value: 'llm_platform desc' },
    { label: 'Model A-Z', value: 'llm_model asc' },
    { label: 'Model Z-A', value: 'llm_model desc' },
    { label: 'Budget (High to Low)', value: 'monthly_budget desc' },
    { label: 'Budget (Low to High)', value: 'monthly_budget asc' },
  ];

  const currentSorting = `${filters.sortBy || 'created_at'} ${filters.sortOrder || 'desc'}`;

  // Use production connection as featured connection
  const otherConnections = llmConnections || [];

  return (
    <div>
      <div className="container">
        {!isModelDataLoading && !isProductionLoading ? (
          <div>
            <div>
              <div className="title_container">
                <div className="title">{t('dataModels.dataModels')}</div>
                <Button
                  appearance="primary"
                  size="m"
                  onClick={() => navigate('/create-llm-connection')}
                >
                  {'Create LLM Connection'}
                </Button>
              </div>
              <div className="search-panel">
                <div className="models-filter-div">
                  <FormSelect
                    label=""
                    name="llmPlatform"
                    placeholder={'Platform'}
                    options={platformOptions}
                    onSelectionChange={(selection) =>
                      handleFilterChange('llmPlatform', selection?.value === 'all' ? '' : selection?.value)
                    }
                    defaultValue={filters?.llmPlatform || 'all'}
                  />
                  <FormSelect
                    label=""
                    name="llmModel"
                    placeholder={'Model'}
                    options={llmModelOptions}
                    onSelectionChange={(selection) =>
                      handleFilterChange('llmModel', selection?.value === 'all' ? '' : selection?.value)
                    }
                    defaultValue={filters?.llmModel || 'all'}
                  />
                  <FormSelect
                    label=""
                    name="environment"
                    placeholder={'Environment'}
                    options={environmentOptions}
                    onSelectionChange={(selection) =>
                      handleFilterChange('environment', selection?.value === 'all' ? '' : selection?.value)
                    }
                    defaultValue={filters?.environment || 'all'}
                  />

                  <FormSelect
                    label=""
                    name="sorting"
                    placeholder={'Sort By'}
                    options={sortOptions}
                    onSelectionChange={(selection) =>
                      handleFilterChange('sorting', selection?.value)
                    }
                    defaultValue={currentSorting}
                  />

                  <div className="filter-reset-button">
                    <Button
                      onClick={() => {
                        setFilters({
                          pageNumber: 1,
                          pageSize: 10,
                          sortBy: 'created_at',
                          sortOrder: 'desc',
                          llmPlatform: '',
                          llmModel: '',
                          environment: '',
                        });
                        setPageIndex(1);
                      }}
                      appearance={ButtonAppearanceTypes.SECONDARY}
                    >
                      {t('global.reset') ?? 'Reset'}
                    </Button>
                  </div>
                </div>
              </div>

              {productionConnection && (
                <div className="m-30-0">
                  <p>Production LLM Connection</p>
                  <div className="grid-container m-30-0">
                    <LLMConnectionCard
                      key={productionConnection.id}
                      llmConnectionId={productionConnection.id}
                      llmConnectionName={productionConnection.connectionName}
                      isActive={productionConnection.connectionStatus === 'active'}
                      deploymentEnv={productionConnection.environment}
                      budgetStatus={productionConnection.budgetStatus}
                      platform={productionConnection.llmPlatform}
                      model={productionConnection.llmModel}
                    />
                  </div>
                </div>
              )}

              {otherConnections?.length > 0 ? (
                <div>
                  <p>Other LLM Connections</p>
                  <div className="grid-container m-30-0">
                    {otherConnections?.map((llmConnection: LLMConnection) => {
                      return (
                        <LLMConnectionCard
                          key={llmConnection.id}
                          llmConnectionId={llmConnection.id}
                          llmConnectionName={llmConnection.connectionName}
                          isActive={llmConnection.connectionStatus === 'active'}
                          deploymentEnv={llmConnection.environment}
                          budgetStatus={llmConnection.budgetStatus}
                          platform={llmConnection.llmPlatform}
                          model={llmConnection.llmModel}
                        />
                      );
                    })}
                  </div>
                </div>
              ) : !productionConnection ? (
                <NoDataView text={t('dataModels.noModels') ?? 'No LLM connections found'} />
              ) : null}

              {(error as any) && (
                <div className="error-message" style={{ color: 'red', padding: '20px' }}>
                  <p>Error loading LLM connections. Please try again.</p>
                </div>
              )}
            </div>
            <Pagination
              pageCount={totalPages}
              pageIndex={pageIndex}
              canPreviousPage={pageIndex > 1}
              canNextPage={pageIndex < totalPages}
              onPageChange={setPageIndex}
            />
          </div>
        ) : (
          <CircularSpinner />
        )}
      </div>
    </div>
  );
};

export default LLMConnections;
