import {
  Badge,
  Box,
  Button,
  Card,
  CardBody,
  Flex,
  Heading,
  HStack,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
  VStack,
} from '@chakra-ui/react';
import { Link, useParams } from 'react-router-dom';
import { useSessionParticipantsQuery, useSessionQuery } from '@/api/caricueApi';
import { errorMessage } from '@/api/baseQuery';
import { EmptyState, ErrorState, LoadingState } from '@/components/StateViews';
import { formatDateTime } from '@/utils/insightFormat';
import { joinName, rosterNameIfDifferent } from '@/utils/participantLabel';

/**
 * Per-student submission index for a session.
 *
 * Kept separate from the live dashboard and reflection flow so teachers can
 * review who answered what without wading through aggregate insights.
 */
export function SessionSubmissionsPage() {
  const { id } = useParams<{ id: string }>();
  const sessionId = Number(id);

  const session = useSessionQuery(sessionId);
  const participants = useSessionParticipantsQuery(sessionId);

  if (session.isLoading || participants.isLoading) {
    return <LoadingState label="Loading submissions…" />;
  }
  if (session.isError || !session.data) {
    return (
      <ErrorState
        message={errorMessage(session.error, 'Session not found.')}
        onRetry={() => void session.refetch()}
      />
    );
  }
  if (participants.isError || !participants.data) {
    return (
      <ErrorState
        message={errorMessage(participants.error, 'Could not load submissions.')}
        onRetry={() => void participants.refetch()}
      />
    );
  }

  const data = session.data;
  const rows = [...participants.data].sort((a, b) => {
    if (a.has_submitted !== b.has_submitted) return a.has_submitted ? -1 : 1;
    const aTime = a.submitted_at ?? a.created_at;
    const bTime = b.submitted_at ?? b.created_at;
    return aTime.localeCompare(bTime);
  });
  const submitted = rows.filter((p) => p.has_submitted);

  return (
    <VStack spacing={5} align="stretch">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap={3}>
        <Box>
          <Heading size="lg">Submissions</Heading>
          <Text color="gray.600">
            {data.activity_title} · {data.classroom_name} · code {data.code}
          </Text>
          <Text fontSize="sm" color="gray.600" mt={1}>
            {submitted.length} submitted
            {rows.length !== submitted.length
              ? ` · ${rows.length - submitted.length} joined but not submitted`
              : ''}
          </Text>
        </Box>
        <HStack wrap="wrap">
          <Button as={Link} to={`/app/sessions/${sessionId}`} variant="outline" size="sm">
            Live results
          </Button>
          <Button
            as={Link}
            to={`/app/sessions/${sessionId}/reflection`}
            variant="outline"
            size="sm"
          >
            Reflection
          </Button>
        </HStack>
      </Flex>

      {submitted.length === 0 ? (
        <EmptyState
          title="No submissions yet"
          description={
            data.status === 'open'
              ? 'Students can still join and submit while the session is open.'
              : 'Nobody submitted before this session closed.'
          }
          action={
            data.status === 'open' ? (
              <Button as={Link} to={`/app/sessions/${sessionId}/launch`} variant="accent">
                Show join code
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Card borderWidth="1px" borderColor="sand.200">
          <CardBody overflowX="auto">
            <Table size="sm">
              <Thead>
                <Tr>
                  <Th>Name at submission</Th>
                  <Th>Roster name</Th>
                  <Th>Submitted</Th>
                  <Th isNumeric>Answers</Th>
                  <Th />
                </Tr>
              </Thead>
              <Tbody>
                {submitted.map((participant) => {
                  const roster = rosterNameIfDifferent(participant);
                  return (
                    <Tr key={participant.id}>
                      <Td fontWeight="600">{joinName(participant)}</Td>
                      <Td color="gray.600">{roster ?? '—'}</Td>
                      <Td whiteSpace="nowrap">
                        {participant.submitted_at
                          ? formatDateTime(participant.submitted_at)
                          : '—'}
                      </Td>
                      <Td isNumeric>{participant.responses.length}</Td>
                      <Td>
                        <Button
                          as={Link}
                          to={`/app/sessions/${sessionId}/submissions/${participant.id}`}
                          size="sm"
                          variant="outline"
                        >
                          View
                        </Button>
                      </Td>
                    </Tr>
                  );
                })}
              </Tbody>
            </Table>
          </CardBody>
        </Card>
      )}

      {rows.some((p) => !p.has_submitted) && (
        <Box>
          <Heading size="sm" mb={2}>
            Joined, not submitted
          </Heading>
          <Card borderWidth="1px" borderColor="sand.200">
            <CardBody overflowX="auto">
              <Table size="sm">
                <Tbody>
                  {rows
                    .filter((p) => !p.has_submitted)
                    .map((participant) => (
                      <Tr key={participant.id}>
                        <Td fontWeight="600">{joinName(participant)}</Td>
                        <Td>
                          <Badge colorScheme="gray" variant="subtle">
                            No submission
                          </Badge>
                        </Td>
                      </Tr>
                    ))}
                </Tbody>
              </Table>
            </CardBody>
          </Card>
        </Box>
      )}
    </VStack>
  );
}
