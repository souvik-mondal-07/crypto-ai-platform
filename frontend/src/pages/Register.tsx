import { AuthLayout } from "../components/auth/AuthLayout";
import { RegisterForm } from "../components/auth/RegisterForm";

export function Register() {
  return (
    <AuthLayout title="Create your account" subtitle="Join Crypto AI Platform">
      <RegisterForm />
    </AuthLayout>
  );
}
