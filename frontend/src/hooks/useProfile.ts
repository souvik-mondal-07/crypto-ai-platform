import { useCallback, useEffect, useState } from "react";

import { profileApi } from "../services/api/profile.api";
import { useAuthStore } from "../store/authStore";
import type { ChangePasswordPayload, Profile } from "../types/userFeatures";
import { toErrorMessage } from "../utils/apiErrors";

/** Profile (name / email / created date), name updates and password change for the signed-in user. */
export function useProfile() {
  const setUser = useAuthStore((state) => state.setUser);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    profileApi
      .get()
      .then((result) => {
        if (cancelled) return;
        setProfile(result);
        setLoading(false);
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        setError(toErrorMessage(caught, "Your profile could not be loaded."));
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);

  /** Resolves to an error message, or null on success. */
  const updateName = useCallback(
    async (name: string): Promise<string | null> => {
      try {
        const updated = await profileApi.updateName(name);
        setProfile(updated);
        setUser(updated); // header etc. show the server-confirmed name
        return null;
      } catch (caught) {
        return toErrorMessage(caught, "Your name could not be updated.");
      }
    },
    [setUser]
  );

  const changePassword = useCallback(async (payload: ChangePasswordPayload): Promise<string | null> => {
    try {
      await profileApi.changePassword(payload);
      return null;
    } catch (caught) {
      return toErrorMessage(caught, "Your password could not be changed.");
    }
  }, []);

  return { profile, loading, error, retry, updateName, changePassword };
}
