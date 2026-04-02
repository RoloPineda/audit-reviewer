import { useState, useCallback, useRef } from "react";
import {
  Flex,
  View,
  Heading,
  Text,
  Button,
  ProgressBar,
  ProgressCircle,
  ActionButton,
  Well,
  Divider,
  TooltipTrigger,
  Tooltip,
  Badge,
  StatusLight,
  Link,
} from "@adobe/react-spectrum";
import ChevronDown from "@spectrum-icons/workflow/ChevronDown";
import ChevronRight from "@spectrum-icons/workflow/ChevronRight";
import Play from "@spectrum-icons/workflow/Play";
import { useAuth } from "../context/AuthContext";
import { evaluateQuestion } from "../api";

const STATUS_CONFIG = {
  met: { badgeVariant: "positive", lightVariant: "positive", label: "Met" },
  not_met: { badgeVariant: "negative", lightVariant: "negative", label: "Not Met" },
  pending: { badgeVariant: "neutral", lightVariant: "neutral", label: "Pending" },
  error: { badgeVariant: "negative", lightVariant: "negative", label: "Error" },
};

function StatusBadge({ status }) {
  if (status === "pending" || !status) {
    return <Badge variant="neutral">Pending</Badge>;
  }
  const config = STATUS_CONFIG[status];
  if (config) {
    return <Badge variant={config.badgeVariant}>{config.label}</Badge>;
  }
  return <Badge variant="info">{status}</Badge>;
}

function StackedSummaryBar({ questions }) {
  const total = questions.length;
  const counts = { met: 0, not_met: 0, pending: 0 };
  for (const q of questions) {
    const s = q.status || "pending";
    if (s in counts) {
      counts[s]++;
    } else if (s === "pending") {
      counts.pending++;
    } else {
      counts.not_met++;
    }
  }

  const segments = [
    { key: "met", count: counts.met },
    { key: "not_met", count: counts.not_met },
    { key: "pending", count: counts.pending },
  ];

  const evaluated = total - counts.pending;

  return (
    <Flex direction="column" gap="size-75" width="100%">
      <ProgressBar
        label={`${evaluated} of ${total} evaluated`}
        value={(evaluated / total) * 100}
        width="100%"
      />
      <Flex gap="size-200" wrap>
        {segments.map((seg) => (
          <StatusLight
            key={seg.key}
            variant={STATUS_CONFIG[seg.key].lightVariant}
          >
            {STATUS_CONFIG[seg.key].label}: {seg.count}
          </StatusLight>
        ))}
      </Flex>
    </Flex>
  );
}

function QuestionCard({ question, onEvaluate, isEvaluating }) {
  const [expanded, setExpanded] = useState(false);
  const [textExpanded, setTextExpanded] = useState(false);
  const status = question.status || "pending";
  const hasResult = status !== "pending" && question.evidence;

  const needsTruncation = question.text.length > 200;
  const displayText =
    needsTruncation && !textExpanded
      ? question.text.slice(0, 200) + "..."
      : question.text;

  return (
    <View
      backgroundColor="gray-50"
      padding="size-300"
      borderRadius="medium"
      borderColor="dark"
      borderWidth="thin"
    >
      <Flex direction="column" gap="size-100">
        <Flex justifyContent="space-between" alignItems="center" wrap gap="size-100">
          <Flex alignItems="center" gap="size-100" flex>
            <Text UNSAFE_style={{ fontWeight: "bold", whiteSpace: "nowrap" }}>
              Q{question.number}
            </Text>
            <StatusBadge status={status} />
            {question.reference && (
              <Text UNSAFE_style={{ fontSize: 12, color: "gray" }}>
                {question.reference}
              </Text>
            )}
          </Flex>
          <Flex gap="size-100" alignItems="center">
            {isEvaluating ? (
              <ProgressCircle
                aria-label={`Evaluating question ${question.number}`}
                isIndeterminate
                size="S"
              />
            ) : (
              <TooltipTrigger>
                <ActionButton
                  onPress={() => onEvaluate(question)}
                  aria-label={`Evaluate question ${question.number}`}
                >
                  <Play size="S" />
                </ActionButton>
                <Tooltip>Evaluate this question against policies</Tooltip>
              </TooltipTrigger>
            )}
          </Flex>
        </Flex>

        <Text UNSAFE_style={{ fontSize: 14, lineHeight: 1.5 }}>
          {displayText}
          {needsTruncation && (
            <>
              {" "}
              <Link isQuiet onPress={() => setTextExpanded(!textExpanded)}>
                {textExpanded ? "show less" : "show more"}
              </Link>
            </>
          )}
        </Text>

        {hasResult && (
          <>
            <ActionButton
              isQuiet
              onPress={() => setExpanded(!expanded)}
              aria-label={expanded ? "Collapse evidence" : "Expand evidence"}
            >
              {expanded ? <ChevronDown /> : <ChevronRight />}
              <Text UNSAFE_style={{ fontWeight: 600 }}>
                View Evidence
              </Text>
            </ActionButton>

            {expanded && (
              <Well>
                <Flex direction="column" gap="size-100">
                  <Text UNSAFE_style={{ whiteSpace: "pre-wrap" }}>
                    {question.evidence}
                  </Text>
                  {question.citation && (
                    <>
                      <Divider size="S" />
                      <Text UNSAFE_style={{ fontStyle: "italic", fontSize: 13 }}>
                        Citation: {question.citation}
                      </Text>
                    </>
                  )}
                </Flex>
              </Well>
            )}
          </>
        )}
      </Flex>
    </View>
  );
}

export default function ResultsPage({ data, onError, onLogout }) {
  const { getAuthHeader } = useAuth();
  const [questions, setQuestions] = useState(() =>
    data.questions.map((q) => ({ ...q, status: "pending", evidence: null, citation: null }))
  );
  const [isEvaluatingAll, setIsEvaluatingAll] = useState(false);
  const [evaluatingIndex, setEvaluatingIndex] = useState(null);
  const [evaluatingQuestionNum, setEvaluatingQuestionNum] = useState(null);
  const cancelRef = useRef(false);
  const questionsRef = useRef(questions);
  questionsRef.current = questions;

  const evaluatedCount = questions.filter(
    (q) => q.status && q.status !== "pending"
  ).length;

  const updateQuestion = useCallback((index, result) => {
    setQuestions((prev) => {
      const next = [...prev];
      next[index] = {
        ...next[index],
        status: result.status,
        evidence: result.evidence,
        citation: result.citation,
      };
      return next;
    });
  }, []);

  async function evaluateSingle(question) {
    const index = questions.findIndex((q) => q.number === question.number);
    if (index === -1) return;

    setEvaluatingQuestionNum(question.number);
    try {
      const result = await evaluateQuestion(question.text, getAuthHeader());
      updateQuestion(index, result);
    } catch (err) {
      updateQuestion(index, { status: "error", evidence: err.message, citation: null });
      onError(`Failed to evaluate Q${question.number}: ${err.message}`);
    } finally {
      setEvaluatingQuestionNum(null);
    }
  }

  async function evaluateAll() {
    cancelRef.current = false;
    setIsEvaluatingAll(true);

    for (let i = 0; i < questions.length; i++) {
      if (cancelRef.current) break;
      const currentStatus = questionsRef.current[i].status;
      if (currentStatus && currentStatus !== "pending") continue;

      setEvaluatingIndex(i);
      setEvaluatingQuestionNum(questions[i].number);

      try {
        const result = await evaluateQuestion(
          questions[i].text,
          getAuthHeader()
        );
        if (cancelRef.current) break;
        updateQuestion(i, result);
      } catch (err) {
        if (cancelRef.current) break;
        updateQuestion(i, { status: "error", evidence: err.message, citation: null });
        onError(`Failed to evaluate Q${questions[i].number}: ${err.message}`);
      }
    }

    setIsEvaluatingAll(false);
    setEvaluatingIndex(null);
    setEvaluatingQuestionNum(null);
  }

  function cancelEvaluation() {
    cancelRef.current = true;
  }

  const title = data.metadata?.submission_item || "Audit Results";
  const aplRef = data.metadata?.apl_reference;

  return (
    <Flex direction="column" minHeight="100vh">
      <View
        backgroundColor="gray-50"
        paddingX="size-400"
        paddingY="size-200"
        borderBottomWidth="thin"
        borderBottomColor="dark"
      >
        <Flex
          justifyContent="space-between"
          alignItems="center"
          wrap
          gap="size-100"
        >
          <Flex alignItems="baseline" gap="size-150" wrap>
            <Heading level={3} margin="size-0">
              {title}
            </Heading>
            {aplRef && (
              <Text UNSAFE_style={{ color: "gray", fontSize: 14 }}>
                {aplRef}
              </Text>
            )}
          </Flex>
          <Button variant="secondary" style="outline" onPress={onLogout}>
            Log Out
          </Button>
        </Flex>
      </View>

      <Flex
        direction="column"
        gap="size-300"
        maxWidth={900}
        marginX="auto"
        width="100%"
        padding="size-300"
      >
        <StackedSummaryBar questions={questions} />

        <Flex alignItems="center" gap="size-200" wrap>
          {isEvaluatingAll ? (
            <Button variant="negative" onPress={cancelEvaluation}>
              Stop
            </Button>
          ) : (
            <Button variant="accent" onPress={evaluateAll}>
              Evaluate All
            </Button>
          )}

          {isEvaluatingAll && (
            <View flex minWidth={200}>
              <ProgressBar
                label={`Evaluating Q${evaluatingQuestionNum || ""}... (${evaluatedCount}/${questions.length})`}
                value={(evaluatedCount / questions.length) * 100}
              />
            </View>
          )}
        </Flex>

        <Flex direction="column" gap="size-200">
          {questions.map((q) => (
            <QuestionCard
              key={q.number}
              question={q}
              onEvaluate={evaluateSingle}
              isEvaluating={
                isEvaluatingAll || evaluatingQuestionNum === q.number
              }
            />
          ))}
        </Flex>
      </Flex>
    </Flex>
  );
}