import { ChangePasswordForm } from "../components/profile/ChangePasswordForm";
import { Loader } from "../components/common/Loader";
import { RetryError } from "../components/common/RetryError";
import { AppShell } from "../components/layout/AppShell";
import { ProfileForm } from "../components/profile/ProfileForm";
import { useProfile } from "../hooks/useProfile";

/** /profile — the signed-in user's name, email and password. */
export function Profile() {
  const { profile, loading, error, retry, updateName, changePassword } = useProfile();

  return (
    <AppShell>
      <h1 className="page-title">Profile</h1>
      <p className="page-subtitle">Your account details.</p>

      <div className="mt-6 max-w-xl space-y-4">
        {error ? (
          <RetryError message={error} onRetry={retry} />
        ) : loading || profile === null ? (
          <Loader label="Loading your profile..." />
        ) : (
          <>
            <ProfileForm profile={profile} onSave={updateName} />
            <ChangePasswordForm onChange={changePassword} />
          </>
        )}
      </div>
    </AppShell>
  );
}
