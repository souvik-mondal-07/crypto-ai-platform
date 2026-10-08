import { AuthLayout } from "../components/auth/AuthLayout";
import { LoginForm } from "../components/auth/LoginForm";

export function Login() {
  return (
    <AuthLayout title="Log in" subtitle="Welcome back to Crypto AI Platform">
      <LoginForm />
    </AuthLayout>
  );
}
