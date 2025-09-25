export const userManagementEndpoints = {
  FETCH_USERS: (): string => `/rag-search/accounts/users`,
  ADD_USER: (): string => `/rag-search/accounts/add`,
  CHECK_ACCOUNT_AVAILABILITY: (): string => `/rag-search/accounts/exists`,
  EDIT_USER: (): string => `/rag-search/accounts/edit`,
  DELETE_USER: (): string => `/rag-search/accounts/delete`,
  FETCH_USER_ROLES: (): string => `/rag-search/accounts/user-role`,
};


export const authEndpoints = {
  GET_EXTENDED_COOKIE: () :string => `/rag-search/auth/jwt/extend`,
  LOGOUT: (): string => `/rag-search/accounts/logout`
}
