export interface User {
  id: string;
  name: string;
  email: string;
  role: string;
  created_at: string;
}

export interface RegisterRequest {
  name: string;
  email: string;
  password: string;
  confirm_password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterResponse {
  user: User;
  message: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in_minutes: number;
}

export interface AuthResponse {
  user: User;
  token: TokenResponse;
}

export interface LogoutResponse {
  message: string;
}
