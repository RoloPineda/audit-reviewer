import { useCallback, useState } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useNavigate,
} from "react-router-dom";
import { Provider, defaultTheme } from "@adobe/react-spectrum";
import { ToastContainer, ToastQueue } from "@react-spectrum/toast";
import { AuthProvider, useAuth } from "./context/AuthContext";
import LoginPage from "./pages/LoginPage";
import UploadPage from "./pages/UploadPage";
import ResultsPage from "./pages/ResultsPage";

function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }
  return children;
}

function AppRoutes() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [questionnaireData, setQuestionnaireData] = useState(null);

  const showError = useCallback((message) => {
    ToastQueue.negative(message, { timeout: 5000 });
  }, []);

  function handleLogin() {
    navigate("/upload", { replace: true });
  }

  function handleUploadComplete(data) {
    setQuestionnaireData(data);
    navigate("/results", { replace: true });
  }

  function handleLogout() {
    logout();
    setQuestionnaireData(null);
    navigate("/", { replace: true });
  }

  return (
    <Routes>
      <Route path="/" element={<LoginPage onLogin={handleLogin} />} />
      <Route
        path="/upload"
        element={
          <ProtectedRoute>
            <UploadPage
              onUploadComplete={handleUploadComplete}
              onError={showError}
            />
          </ProtectedRoute>
        }
      />
      <Route
        path="/results"
        element={
          <ProtectedRoute>
            {questionnaireData ? (
              <ResultsPage
                data={questionnaireData}
                onError={showError}
                onLogout={handleLogout}
              />
            ) : (
              <Navigate to="/upload" replace />
            )}
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <Provider theme={defaultTheme} colorScheme="light">
      <BrowserRouter>
        <AuthProvider>
          <AppRoutes />
          <ToastContainer />
        </AuthProvider>
      </BrowserRouter>
    </Provider>
  );
}