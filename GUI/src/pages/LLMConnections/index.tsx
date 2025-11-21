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
import { fetchLLMConnectionsPaginated, LLMConnectionFilters, LLMConnection, getProductionConnection, ProductionConnectionFilters } from 'services/llmConnections';
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

  // Fetch production connection separately with potential filters
  const [productionFilters, setProductionFilters] = useState<ProductionConnectionFilters>({
    sortBy: 'created_at',
    sortOrder: 'desc',
    llmPlatform: '',
    llmModel: '',
  });
  
  const { data: productionConnection, isLoading: isProductionLoading } = useQuery({
    queryKey: llmConnectionsQueryKeys.production(productionFilters),
    queryFn: () => getProductionConnection(productionFilters),
  });


  const llmConnections = connectionsResponse;
  const totalPages = connectionsResponse?.[0]?.totalPages || 1;

  // Update filters when pageIndex changes
  useEffect(() => {
    setFilters(prev => ({ ...prev, pageNumber: pageIndex }));
  }, [pageIndex]);

  // Sync production filters with main filters on component mount
  useEffect(() => {
    setProductionFilters(prev => ({
      ...prev,
      llmPlatform: filters.llmPlatform || '',
      llmModel: filters.llmModel || '',
      sortBy: filters.sortBy || 'created_at',
      sortOrder: filters.sortOrder || 'desc',
    }));
  }, [filters.llmPlatform, filters.llmModel, filters.sortBy, filters.sortOrder]);

  const handleFilterChange = (
    name: string,
    value: string | number | undefined | { name: string; id: string }
  ) => {
    let filterUpdate: Partial<LLMConnectionFilters> = {};
    let productionFilterUpdate: Partial<ProductionConnectionFilters> = {};

    if (name === 'sorting') {
      // Handle sorting format - no conversion needed, use snake_case directly
      const sortingValue = value as string;
      const [sortBy, sortOrder] = sortingValue.split(' ');

      filterUpdate = {
        sortBy: sortBy,
        sortOrder: sortOrder as 'asc' | 'desc' 
      };

      productionFilterUpdate = {
        sortBy: sortBy,
        sortOrder: sortOrder as 'asc' | 'desc'
      };
    } else {
      filterUpdate = { [name]: value };

      // Update production filters for relevant fields
      if (name === 'llmPlatform' || name === 'llmModel') {
        productionFilterUpdate = { [name]: value as string };
      }
    }

    setFilters((prevFilters) => ({
      ...prevFilters,
      ...filterUpdate,
    }));

    // Update production filters if relevant
    if (Object.keys(productionFilterUpdate).length > 0) {
      setProductionFilters((prevFilters) => ({
        ...prevFilters,
        ...productionFilterUpdate,
      }));
    }

    // Reset to first page when filters change
    if (name !== 'pageNumber') {
      setPageIndex(1);
    }
  };

  // Platform filter options
  const platformOptions = [
    { label: t('dataModels.filters.allPlatforms'), value: 'all' },
    { label: t('dataModels.platforms.azure'), value: 'azure' },
    { label: t('dataModels.platforms.aws'), value: 'aws' },
  ];

  // LLM Model filter options - these would ideally come from an API
  const llmModelOptions = [
    { label: t('dataModels.filters.allModels'), value: 'all' },
    { label: t('dataModels.models.gpt4Mini'), value: 'gpt-4o-mini' },
    { label: t('dataModels.models.gpt4o'), value: 'gpt-4o' },
    { label: t('dataModels.models.claude35Sonnet'), value: 'anthropic-claude-3.5-sonnet' },
    { label: t('dataModels.models.claude37Sonnet'), value: 'anthropic-claude-3.7-sonnet' },
  ];

  // Environment filter options
  const environmentOptions = [
    { label: t('dataModels.filters.allEnvironments'), value: 'all' },
    { label: t('dataModels.environments.testing'), value: 'testing' },
    { label: t('dataModels.environments.production'), value: 'production' },
  ];

  // Sort options - using snake_case format for backend
  const sortOptions = [
    { label: t('dataModels.sortOptions.createdDateNewest'), value: 'created_at desc' },
    { label: t('dataModels.sortOptions.createdDateOldest'), value: 'created_at asc' },
    { label: t('dataModels.sortOptions.platformAZ'), value: 'llm_platform asc' },
    { label: t('dataModels.sortOptions.platformZA'), value: 'llm_platform desc' },
    { label: t('dataModels.sortOptions.modelAZ'), value: 'llm_model asc' },
    { label: t('dataModels.sortOptions.modelZA'), value: 'llm_model desc' },
    { label: t('dataModels.sortOptions.budgetHighToLow'), value: 'monthly_budget desc' },
    { label: t('dataModels.sortOptions.budgetLowToHigh'), value: 'monthly_budget asc' },
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
                  {t('dataModels.createModel')}
                </Button>
              </div>
              <div className="search-panel">
                <div className="models-filter-div">
                  <FormSelect
                    label=""
                    name="llmPlatform"
                    placeholder={t('dataModels.filters.platform') ?? 'Platform'}
                    options={platformOptions}
                    onSelectionChange={(selection) =>
                      handleFilterChange('llmPlatform', selection?.value === 'all' ? '' : selection?.value)
                    }
                    defaultValue={filters?.llmPlatform || 'all'}
                  />
                  <FormSelect
                    label=""
                    name="llmModel"
                    placeholder={t('dataModels.filters.model') ?? 'Model'}
                    options={llmModelOptions}
                    onSelectionChange={(selection) =>
                      handleFilterChange('llmModel', selection?.value === 'all' ? '' : selection?.value)
                    }
                    defaultValue={filters?.llmModel || 'all'}
                  />
                  <FormSelect
                    label=""
                    name="environment"
                    placeholder={t('dataModels.filters.environment') ?? 'Environment'}
                    options={environmentOptions}
                    onSelectionChange={(selection) =>
                      handleFilterChange('environment', selection?.value === 'all' ? '' : selection?.value)
                    }
                    defaultValue={filters?.environment || 'all'}
                  />

                  <FormSelect
                    label=""
                    name="sorting"
                    placeholder={t('dataModels.filters.sortBy') ?? 'Sort By'}
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
                        setProductionFilters({
                          sortBy: 'created_at',
                          sortOrder: 'desc',
                          llmPlatform: '',
                          llmModel: '',
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

              {productionConnection && filters?.environment !== "testing" && (
                <div className="m-30-0">
                  <p>{t('dataModels.productionConnections')}</p>
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
                  <p>{t('dataModels.otherConnections')}</p>
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
