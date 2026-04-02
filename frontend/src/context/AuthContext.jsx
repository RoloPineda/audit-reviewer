import { createContext, useContext, useState, useCallback } from "react";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [credentials, setCredentials] = useState(null);

  const login = useCallback((username, password) => {
    const encoded = btoa(`${username}:${password}`);
    setCredentials({ username, encoded });
  }, []);

  const logout = useCallback(() => {
    setCredentials(null);
  }, []);

  const getAuthHeader = useCallback(() => {
    if (!credentials) return {};
    return { Authorization: `Basic ${credentials.encoded}` };
  }, [credentials]);

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated: !!credentials,
        username: credentials?.username,
        login,
        logout,
        getAuthHeader,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}