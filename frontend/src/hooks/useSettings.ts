import { useSettingsStore } from "../store/settingsStore";

export function useSettings() {
  return useSettingsStore();
}
