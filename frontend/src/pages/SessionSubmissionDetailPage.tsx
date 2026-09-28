import {
  Badge,
  Box,
  Button,
  Card,
  CardBody,
  Flex,
  Heading,
  HStack,
  Stack,
  Text,
  VStack,
} from '@chakra-ui/react';
import { Link, useParams } from 'react-router-dom';
import { useSessionParticipantsQuery, useSessionQuery } from '@/api/caricueApi';
import { errorMessage } from '@/api/baseQuery';
import { ErrorState, LoadingState } from '@/components/StateViews';
import { formatDateTime } from '@/utils/insightFormat';
import { joinName, rosterNameIfDifferent } from '@/utils/participantLabel';
import type { ParticipantResponse } from '@/api/types';

function answerSummary(response: ParticipantResponse): string {
  if (response.question_type === 'multiple_choice') {
    return response.selected_choice_text ?? '(no choice)';
  }
  if (response.question_type === 'short_text') {
    return response.text_response?.trim() || '(empty)';
  }
  if (response.confidence_value != null) {
    return `Confidence: ${response.confidence_value}`;
  }
  return '—';
}

function correctnessBadge(isCorrect: boolean | null) {
  if (isCorrect === null) return null;
  return (
    <Badge colorScheme={isCorrect ? 'cariteal' : 'coral'} variant="subtle">
      {isCorrect ? 'Correct' : 'Incorrect'}
    </Badge>
  );
}

export function SessionSubmissionDetailPage() {
  const { id, participantId } = useParams<{ id: string; participantId: string }>();
  const sessionId = Number(id);
  const participantPk = Number(participantId);

  const session = useSessionQuery(sessionId);
  const participants = useSessionParticipantsQuery(sessionId);

  if (session.isLoading || participants.isLoading) {
    return <LoadingState label="Loading submission…" />;
  }
  if (session.isError || !session.data) {
    return <ErrorState message={errorMessage(session.error, 'Session not found.')} />;
  }
  if (participants.isError || !participants.data) {
    return <ErrorState message={errorMessage(participants.error)} />;
  }

  const participant = participants.data.find((p) => p.id === participantPk);
  if (!participant) {
    return (
      <VStack align="stretch" spacing={4}>
        <ErrorState
          title="Submission not found"
          message="This participant is not part of this session."
        />
        <Button as={Link} to={`/app/sessions/${sessionId}/submissions`} variant="outline">
          Back to submissions
        </Button>
      </VStack>
    );
  }

  const roster = rosterNameIfDifferent(participant);
  const responses = [...participant.responses].sort(
    (a, b) => a.question_position - b.question_position
  );

  return (
    <VStack spacing={5} align="stretch">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap={3}>
        <Box>
          <Button
            as={Link}
            to={`/app/sessions/${sessionId}/submissions`}
            variant="ghost"
            size="sm"
            mb={2}
          >
            ← All submissions
          </Button>
          <Heading size="lg">{joinName(participant)}</Heading>
          {roster && (
            <Text color="gray.600" fontSize="sm">
              Roster name: {roster}
            </Text>
          )}
          <Text color="gray.600" fontSize="sm" mt={1}>
            {session.data.activity_title} · {session.data.classroom_name}
          </Text>
          {participant.submitted_at && (
            <Text fontSize="sm" color="gray.600">
              Submitted {formatDateTime(participant.submitted_at)}
            </Text>
          )}
        </Box>
        <HStack>
          <Button as={Link} to={`/app/sessions/${sessionId}`} variant="outline" size="sm">
            Live results
          </Button>
        </HStack>
      </Flex>

      {!participant.has_submitted ? (
        <Card borderWidth="1px" borderColor="sand.200">
          <CardBody>
            <Text color="gray.600">
              This student joined as “{joinName(participant)}” but has not submitted yet.
            </Text>
          </CardBody>
        </Card>
      ) : (
        <Stack spacing={4}>
          {responses.map((response) => (
            <Card key={response.id} borderWidth="1px" borderColor="sand.200">
              <CardBody>
                <VStack align="stretch" spacing={2}>
                  <HStack spacing={2} flexWrap="wrap">
                    <Badge colorScheme="ocean" variant="subtle">
                      Q{response.question_position}
                    </Badge>
                    {correctnessBadge(response.is_correct)}
                  </HStack>
                  <Text fontWeight="600">{response.question_prompt}</Text>
                  <Text>{answerSummary(response)}</Text>
                  {response.confidence_value != null &&
                    response.question_type !== 'confidence' && (
                      <Text fontSize="sm" color="gray.600">
                        Confidence: {response.confidence_value}
                      </Text>
                    )}
                </VStack>
              </CardBody>
            </Card>
          ))}
        </Stack>
      )}
    </VStack>
  );
}
