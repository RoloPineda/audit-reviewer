import { useRef, useState } from "react";
import {
  Flex,
  Heading,
  Button,
  ProgressCircle,
  Content,
  IllustratedMessage,
} from "@adobe/react-spectrum";
import Upload from "@spectrum-icons/illustrations/Upload";
import { useAuth } from "../context/AuthContext";
import { uploadQuestionnaire } from "../api";

export default function UploadPage({ onUploadComplete, onError }) {
  const { getAuthHeader, logout } = useAuth();
  const [file, setFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);

  function handleFileChange(e) {
    const selected = e.target.files[0];
    if (selected && selected.type === "application/pdf") {
      setFile(selected);
    } else if (selected) {
      onError("Please select a PDF file");
    }
  }

  function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped && dropped.type === "application/pdf") {
      setFile(dropped);
    } else if (dropped) {
      onError("Please select a PDF file");
    }
  }

  function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }

  function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }

  async function handleUpload() {
    if (!file) return;
    setIsUploading(true);

    try {
      const data = await uploadQuestionnaire(file, getAuthHeader());
      onUploadComplete(data);
    } catch (err) {
      if (err.message === "Invalid credentials") {
        onError("Session expired. Please log in again.");
        logout();
      } else {
        onError(err.message || "Upload failed");
      }
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <Flex
      direction="column"
      alignItems="center"
      justifyContent="center"
      minHeight="100vh"
      gap="size-300"
    >
      <Heading level={2}>Upload Audit Questionnaire</Heading>

      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        style={{
          padding: 48,
          borderRadius: 8,
          border: `2px dashed ${isDragging ? "#0265dc" : "#ccc"}`,
          backgroundColor: isDragging ? "#e8f4ff" : "#fafafa",
          cursor: "pointer",
          textAlign: "center",
          width: "min(90%, 480px)",
          boxSizing: "border-box",
        }}
      >
        {isUploading ? (
          <Flex direction="column" alignItems="center" gap="size-200">
            <ProgressCircle aria-label="Uploading..." isIndeterminate size="L" />
            <span>Processing questionnaire...</span>
          </Flex>
        ) : (
          <Flex direction="column" alignItems="center" gap="size-200">
            <IllustratedMessage>
              <Upload />
              <Heading>
                {file ? file.name : "Drag and drop a PDF here"}
              </Heading>
              <Content>
                {file ? `${(file.size / 1024).toFixed(1)} KB` : "or"}
              </Content>
            </IllustratedMessage>

            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,application/pdf"
              onChange={handleFileChange}
              style={{ display: "none" }}
            />

            {!file && (
              <Button
                variant="secondary"
                onPress={() => fileInputRef.current?.click()}
              >
                Browse Files
              </Button>
            )}

            {file && (
              <Flex gap="size-200">
                <Button variant="secondary" onPress={() => setFile(null)}>
                  Clear
                </Button>
                <Button variant="accent" onPress={handleUpload}>
                  Upload and Process
                </Button>
              </Flex>
            )}
          </Flex>
        )}
      </div>
    </Flex>
  );
}