import { useMutation, useQuery } from '@tanstack/react-query';
import { AuthenticationService, UserCreate, Body_login_api_v1_auth_login_post } from '@/lib/api';
import { clearSession, setSession } from '@/lib/authSession';

export function useUser(enabled = true) {
  return useQuery({
    queryKey: ['user', 'me'],
    queryFn: () => AuthenticationService.getMeApiV1AuthMeGet(),
    retry: false,
    enabled,
  });
}

export function useLogin() {
  return useMutation({
    mutationFn: (data: Body_login_api_v1_auth_login_post) => 
      AuthenticationService.loginApiV1AuthLoginPost(data),
    onSuccess: (response) => {
      if (response.access_token) {
        setSession(response.access_token);
      }
    },
  });
}

export function useRegister() {
  return useMutation({
    mutationFn: (data: UserCreate) => 
      AuthenticationService.registerApiV1AuthRegisterPost(data),
    onSuccess: () => {
      // For registration, we might need a separate login or the register endpoint
      // should return a token. In this app, register returns the User object.
    }
  });
}

export function useLogout() {
  return useMutation({
    mutationFn: () => AuthenticationService.logoutApiV1AuthLogoutPost(),
    onSuccess: () => {
      clearSession();
      window.location.href = '/login';
    },
    onError: () => {
      clearSession();
      window.location.href = '/login';
    },
  });
}

export function logout() {
  AuthenticationService.logoutApiV1AuthLogoutPost().finally(() => {
    clearSession();
    window.location.href = '/login';
  });
}
