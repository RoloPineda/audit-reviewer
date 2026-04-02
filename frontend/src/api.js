const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function checkHealth() {
  const response = await fetch(`${API_URL}/api/health`);
  return response.ok;
}

export async function uploadQuestionnaire(file, authHeader) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_URL}/api/questionnaire`, {
    method: "POST",
    headers: { ...authHeader },
    body: formData,
  });

  if (response.status === 401) {
    throw new Error("Invalid credentials");
  }

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Upload failed (${response.status})`);
  }

  return response.json();
}

export async function evaluateQuestion(question, authHeader) {
  const response = await fetch(`${API_URL}/api/evaluate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeader,
    },
    body: JSON.stringify({ question }),
  });

  if (response.status === 401) {
    throw new Error("Invalid credentials");
  }

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Evaluation failed (${response.status})`);
  }

  return response.json();
}