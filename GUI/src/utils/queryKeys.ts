import { PaginationState, SortingState } from '@tanstack/react-table';


export const authQueryKeys = {
  USER_DETAILS: () => ['rag-search/auth/jwt/userinfo', 'prod'],
  USER_ROLES: (): string[] => ['/accounts/user-role', 'prod'],

};


export const userManagementQueryKeys = {
  getAllEmployees: function (
    pagination?: PaginationState,
    sorting?: SortingState
  ) {
    return ['accounts/users', pagination, sorting].filter(
      (val) => val !== undefined
    );
  },
};
