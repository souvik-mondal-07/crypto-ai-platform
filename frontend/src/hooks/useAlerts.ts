import { useCallback, useEffect, useState } from "react";

import { alertsApi } from "../services/api/alerts.api";
import type { AlertCheckResult, AlertCreate, AlertList, AlertUpdate } from "../types/userFeatures";
import { toErrorMessage } from "../utils/apiErrors";
import { toast } from "../store/toastStore";

/** The signed-in user's price alerts, plus create / update / delete and an explicit "check now". */
export function useAlerts() {
  const [data, setData] = useState<AlertList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [checkResult, setCheckResult] = useState<AlertCheckResult | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    alertsApi
      .list(1, 100)
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setLoading(false);
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        setError(toErrorMessage(caught, "Your alerts could not be loaded."));
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const reload = useCallback(() => setAttempt((value) => value + 1), []);

  const run = useCallback(
    async (action: () => Promise<unknown>, fallback: string, success: string): Promise<boolean> => {
      setBusy(true);
      setActionError(null);
      try {
        await action();
        toast.success(success);
        reload();
        return true;
      } catch (caught) {
        setActionError(toErrorMessage(caught, fallback));
        return false;
      } finally {
        setBusy(false);
      }
    },
    [reload]
  );

  const create = useCallback((payload: AlertCreate) => run(() => alertsApi.create(payload), "The alert could not be created.", "Alert created."), [run]);
  const update = useCallback(
    (id: string, payload: AlertUpdate) => run(() => alertsApi.update(id, payload), "The alert could not be updated.", "Alert updated."),
    [run]
  );
  const remove = useCallback((id: string) => run(() => alertsApi.remove(id), "The alert could not be deleted.", "Alert deleted."), [run]);

  const check = useCallback(async () => {
    setBusy(true);
    setActionError(null);
    try {
      const result = await alertsApi.check();
      setCheckResult(result);
      reload();
    } catch (caught) {
      setActionError(toErrorMessage(caught, "Alerts could not be checked right now."));
    } finally {
      setBusy(false);
    }
  }, [reload]);

  return { data, loading, error, actionError, busy, checkResult, create, update, remove, check, retry: reload };
}
