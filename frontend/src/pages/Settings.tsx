import { Loader } from "../components/common/Loader";
import { Notice } from "../components/common/Notice";
import { RetryError } from "../components/common/RetryError";
import { AppShell } from "../components/layout/AppShell";
import { useAuthStore } from "../store/authStore";
import { useSettingsStore } from "../store/settingsStore";
import { useThemePreference } from "../hooks/useThemePreference";

/** /settings — theme and notification preferences, saved to the user's account. */
export function Settings() {
  const userId = useAuthStore((state) => state.user?.id ?? null);
  const status = useSettingsStore((state) => state.status);
  const error = useSettingsStore((state) => state.error);
  const settings = useSettingsStore((state) => state.settings);
  const saveError = useSettingsStore((state) => state.saveError);
  const saving = useSettingsStore((state) => state.saving);
  const load = useSettingsStore((state) => state.load);
  const update = useSettingsStore((state) => state.update);
  const { theme, choose } = useThemePreference();

  return (
    <AppShell>
      <h1 className="page-title">Settings</h1>
      <p className="page-subtitle">Preferences are saved to your account.</p>

      <div className="mt-6 max-w-xl space-y-4">
        {status === "error" ? (
          <RetryError message={error ?? "Your settings could not be loaded."} onRetry={() => void load(userId)} />
        ) : status !== "ready" ? (
          <Loader label="Loading your settings..." />
        ) : (
          <>
            {saveError && <Notice kind="error" message={saveError} />}

            <section aria-labelledby="theme-heading" className="card card-pad">
              <h2 id="theme-heading" className="text-sm font-semibold text-slate-800 dark:text-slate-100">Appearance</h2>
              <div role="radiogroup" aria-label="Theme" className="segmented mt-3">
                {(["light", "dark"] as const).map((option) => (
                  <button
                    key={option}
                    type="button"
                    role="radio"
                    aria-checked={theme === option}
                    onClick={() => choose(option)}
                    className={`segmented-item !px-4 !py-1.5 !text-sm capitalize ${theme === option ? "segmented-item-active" : ""}`}
                  >
                    {option}
                  </button>
                ))}
              </div>
              <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">Prices are shown in USD.</p>
            </section>

            <section aria-labelledby="notifications-heading" className="card card-pad">
              <h2 id="notifications-heading" className="text-sm font-semibold text-slate-800 dark:text-slate-100">Notifications</h2>
              <label className="mt-3 flex items-start gap-3 text-sm text-slate-700 dark:text-slate-200">
                <input
                  type="checkbox"
                  checked={settings.notifications.price_alerts}
                  disabled={saving}
                  onChange={(event) => void update({ notifications: { price_alerts: event.target.checked } })}
                  className="mt-0.5 h-4 w-4 rounded border-slate-300"
                />
                <span>
                  Show a banner on the Alerts page when a price alert has triggered
                  <span className="block text-xs text-slate-500 dark:text-slate-400">In-app only — no email or push notifications are sent.</span>
                </span>
              </label>
            </section>
          </>
        )}
      </div>
    </AppShell>
  );
}
