import { useState } from "react";
import {
  Flex,
  View,
  Heading,
  TextField,
  Button,
  Form,
} from "@adobe/react-spectrum";
import { useAuth } from "../context/AuthContext";
import { checkHealth } from "../api";

export default function LoginPage({ onLogin }) {
  const { login, getAuthHeader } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    login(username, password);

    try {
      const encoded = btoa(`${username}:${password}`);
      const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
      const response = await fetch(`${API_URL}/api/questionnaire`, {
        method: "POST",
        headers: { Authorization: `Basic ${encoded}` },
        body: new FormData(),
      });

      if (response.status === 401) {
        setError("Invalid username or password");
        setIsLoading(false);
        return;
      }

      onLogin();
    } catch {
      try {
        const healthy = await checkHealth();
        if (healthy) {
          onLogin();
        } else {
          setError("Cannot connect to backend server");
        }
      } catch {
        setError("Cannot connect to backend server");
      }
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Flex
      direction="column"
      alignItems="center"
      justifyContent="center"
      minHeight="100vh"
    >
      <View
        backgroundColor="gray-50"
        padding="size-500"
        borderRadius="medium"
        borderColor="dark"
        borderWidth="thin"
        width={{ base: "90%", M: "size-4600" }}
      >
        <Form onSubmit={handleSubmit}>
          <Flex direction="column" gap="size-200">
            <Heading level={2}>Compliance Audit Tool</Heading>

            <TextField
              label="Username"
              value={username}
              onChange={setUsername}
              isRequired
              autoFocus
            />

            <TextField
              label="Password"
              type="password"
              value={password}
              onChange={setPassword}
              isRequired
            />

            {error && (
              <View
                backgroundColor="negative"
                padding="size-100"
                borderRadius="small"
              >
                <span style={{ color: "white", fontSize: 14 }}>{error}</span>
              </View>
            )}

            <Button
              variant="accent"
              type="submit"
              isPending={isLoading}
              width="100%"
              marginTop="size-100"
            >
              Log In
            </Button>
          </Flex>
        </Form>
      </View>
    </Flex>
  );
}