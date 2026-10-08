import { useEffect } from "react";
import { BrowserRouter } from "react-router-dom";

import { AppRoutes } from "./routes/AppRoutes";
import { useAuthStore } from "./store/authStore";
import { ThemeProvider } from "./context/ThemeContext";

function App() {
  const initializeAuth = useAuthStore((state) => state.initializeAuth);

  // Runs once on app startup: if a token is stored, verify it against
  // /auth/me before trusting it — see docs/authentication.md for the
  // full page-refresh flow this implements.
  useEffect(() => {
    initializeAuth();
  }, [initializeAuth]);

  return (
    <ThemeProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
