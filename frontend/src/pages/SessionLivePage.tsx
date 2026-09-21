import { useState } from 'react';
import {
  Alert,
  AlertIcon,
  Badge,
  Box,
  Button,
  Card,
  CardBody,
  Flex,
  Heading,
  HStack,
  SimpleGrid,
  Stack,
  Switch,
  Text,
  useToast,
  VStack,
} from '@chakra-ui/react';
import { Link, useParams } from 'react-router-dom';
import {
  caricueApi,
  useCloseSessionMutation,
  useSessionDashboardQuery,
} from '@/api/caricueApi';
import { errorMessage } from '@/api/baseQuery';
import { ErrorState, LoadingState } from '@/components/StateViews';
import { StatTile } from '@/components/StatTile';
import { FactBadge } from '@/components/FactBadge';
import { ConfidenceChart } from '@/components/ConfidenceChart';
import { QuestionInsightCard } from '@/components/QuestionInsightCard';
import { SuggestionPanel } from '@/components/SuggestionPanel';
import { AttentionPanel } from '@/components/AttentionPanel';
import { MisconceptionCardPanel } from '@/components/MisconceptionCardPanel';
import { SessionComparisonPanel } from '@/components/SessionComparisonPanel';
import {
  formatCompletion,
  formatConfidence,
  formatPercent,
  formatRelativeTime,
} from '@/utils/insightFormat';

/** Fallback until the server tells us its configured cadence. */
const DEFAULT_POLL_SECONDS = 4;

/**
 * Live results, refreshed by polling.
 *
 * Polling (not WebSockets) is a deliberate MVP choice: a classroom check runs
 * for a few minutes with a handful of devices, and polling survives flaky
 * networks and simple reverse-proxy setups without extra infrastructure.
 */
export function SessionLivePage() {
  const { id } = useParams<{ id: string }>();
  const sessionId = Number(id);
  const toast = useToast();
  // The only genuine piece of local state: whether the teacher wants polling.
  const [autoRefreshWanted, setAutoRefreshWanted] = useState(true);

  // Reads the cache without issuing a request, so the poll cadence and the
  // stop-when-closed rule can be derived rather than mirrored into state.
  const cached = caricueApi.endpoints.sessionDashboard.useQueryState(sessionId);
  const pollSeconds = cached.data?.poll_interval_seconds ?? DEFAULT_POLL_SECONDS;
  const sessionIsOpen = cached.data?.session.status !== 'closed';
  const autoRefresh = autoRefreshWanted && sessionIsOpen;

  const { data, isLoading, isError, error, isFetching, refetch, fulfilledTimeStamp } =
    useSessionDashboardQuery(sessionId, {
      // Polling, not WebSockets; it stops on its own once the session closes
      // because the numbers can no longer change.
      pollingInterval: autoRefresh ? pollSeconds * 1000 : 0,
      refetchOnMountOrArgChange: true,
    });
  const [closeSession, closeState] = useCloseSessionMutation();
  const lastUpdated = fulfilledTimeStamp ? new Date(fulfilledTimeStamp).toISOString() : null;

  if (isLoading) return <LoadingState label="Loading live results…" />;
  if (isError || !data) {
    return (
      <ErrorState
        message={errorMessage(error, 'Could not load this session.')}
        onRetry={() => void refetch()}
      />
    );
  }

  const { session, facts, suggestions, misconception_cards, comparison } = data;
  const isOpen = session.status === 'open';

  async function handleClose() {
    try {
      await closeSession(sessionId).unwrap();
      toast({
        title: 'Session closed',
        description: 'Record what you will do next on the reflection screen.',
        status: 'success',
      });
    } catch (closeError) {
      toast({ title: errorMessage(closeError), status: 'error' });
    }
  }

  return (
    <VStack spacing={5} align="stretch">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap={3}>
        <Box>
          <HStack>
            <Heading size="lg">{session.activity_title}</Heading>
            <Badge colorScheme={isOpen ? 'cariteal' : 'gray'} variant="solid">
              {session.status}
            </Badge>
          </HStack>
          <Text color="gray.600">
            {session.classroom_name}
            {session.activity_topic ? ` · ${session.activity_topic}` : ''} · code {session.code}
          </Text>
        </Box>

        <HStack spacing={2} wrap="wrap">
          <Button
            as={Link}
            to={`/app/sessions/${sessionId}/launch`}
            variant="outline"
            size="sm"
          >
            Show code
          </Button>
          {isOpen ? (
            <Button
              variant="accent"
              size="sm"
              onClick={handleClose}
              isLoading={closeState.isLoading}
              loadingText="Closing…"
            >
              Close session
            </Button>
          ) : (
            <Button
              as={Link}
              to={`/app/sessions/${sessionId}/reflection`}
              variant="accent"
              size="sm"
            >
              {session.has_reflection ? 'View reflection' : 'Record next step'}
            </Button>
          )}
        </HStack>
      </Flex>

      <Flex
        justify="space-between"
        align="center"
        wrap="wrap"
        gap={3}
        bg="white"
        borderWidth="1px"
        borderColor="sand.200"
        borderRadius="md"
        px={4}
        py={2}
      >
        <HStack spacing={3}>
          <Switch
            id="auto-refresh"
            isChecked={autoRefresh}
            onChange={(e) => setAutoRefreshWanted(e.target.checked)}
            colorScheme="cariteal"
            isDisabled={!isOpen}
          />
          <Text as="label" htmlFor="auto-refresh" fontSize="sm" color="gray.700">
            Auto-refresh every {pollSeconds}s
          </Text>
        </HStack>
        <HStack spacing={3}>
          <Text fontSize="sm" color="gray.600" aria-live="polite">
            {isFetching ? 'Updating…' : `Updated ${formatRelativeTime(lastUpdated)}`}
          </Text>
          <Button
            size="xs"
            variant="ghost"
            onClick={() => void refetch()}
            isLoading={isFetching}
          >
            Refresh now
          </Button>
        </HStack>
      </Flex>

      {!isOpen && !session.has_reflection && (
        <Alert status="info" borderRadius="md">
          <AlertIcon />
          <Box>
            <Text>
              This session is closed. The last step of the loop is deciding what to do with the
              evidence.
            </Text>
            <Button
              as={Link}
              to={`/app/sessions/${sessionId}/reflection`}
              size="sm"
              variant="accent"
              mt={2}
            >
              Record what you will do next
            </Button>
          </Box>
        </Alert>
      )}

      <SimpleGrid columns={{ base: 1, sm: 2, lg: 4 }} spacing={4}>
        <StatTile
          label="Participants"
          value={String(facts.participant_count)}
          help={formatCompletion(facts)}
        />
        <StatTile
          label="Completion"
          value={formatPercent(facts.completion_percentage)}
          help={
            facts.roster_size > 0
              ? `Roster of ${facts.roster_size}`
              : 'No roster imported for this class'
          }
          accent="cariteal"
        />
        <StatTile
          label="Auto-scored correct"
          value={formatPercent(facts.overall_correctness_percentage)}
          help={
            facts.has_auto_scored_data
              ? `${facts.auto_scored_response_count} scored answers`
              : 'No auto-scored questions answered yet'
          }
          accent="coral"
        />
        <StatTile
          label="Average confidence"
          value={formatConfidence(facts.average_confidence)}
          help={facts.has_confidence_data ? 'Self-reported, 1-5' : 'Not collected'}
          accent="gray"
        />
      </SimpleGrid>

      <SimpleGrid columns={{ base: 1, xl: 3 }} spacing={5}>
        <VStack spacing={5} align="stretch" gridColumn={{ xl: 'span 2' }}>
          {facts.lowest_correctness_questions.length > 0 && (
            <Card borderWidth="1px" borderColor="sand.200">
              <CardBody>
                <HStack justify="space-between" mb={3}>
                  <Heading size="sm" color="ocean.800">
                    Weakest questions
                  </Heading>
                  <FactBadge />
                </HStack>
                <Stack spacing={2}>
                  {facts.lowest_correctness_questions.map((item) => (
                    <HStack
                      key={item.question_id}
                      justify="space-between"
                      bg={item.below_threshold ? 'coral.50' : 'sand.100'}
                      px={3}
                      py={2}
                      borderRadius="md"
                      gap={3}
                    >
                      <Text fontSize="sm">
                        Q{item.position}. {item.prompt}
                      </Text>
                      <Badge
                        colorScheme={item.below_threshold ? 'coral' : 'gray'}
                        variant="subtle"
                        whiteSpace="nowrap"
                      >
                        {formatPercent(item.correctness_percentage)}
                      </Badge>
                    </HStack>
                  ))}
                </Stack>
              </CardBody>
            </Card>
          )}

          <Box>
            <Heading size="md" mb={3}>
              Question by question
            </Heading>
            <VStack spacing={4} align="stretch">
              {facts.questions.map((question) => (
                <QuestionInsightCard key={question.question_id} question={question} />
              ))}
            </VStack>
          </Box>
        </VStack>

        <VStack spacing={5} align="stretch">
          {facts.has_confidence_data && (
            <Card borderWidth="1px" borderColor="sand.200">
              <CardBody>
                <HStack justify="space-between" mb={3}>
                  <Heading size="sm" color="ocean.800">
                    Confidence across the class
                  </Heading>
                  <FactBadge />
                </HStack>
                <ConfidenceChart
                  distribution={facts.confidence_distribution}
                  label="Confidence distribution across the session"
                />
              </CardBody>
            </Card>
          )}

          {!isOpen && comparison && (
            <SessionComparisonPanel comparison={comparison} classroomId={session.classroom} />
          )}
          {facts.submitted_count > 0 && (
            <MisconceptionCardPanel
              sessionId={sessionId}
              cards={misconception_cards ?? []}
            />
          )}
          <AttentionPanel facts={facts} />
          <SuggestionPanel suggestions={suggestions} />
        </VStack>
      </SimpleGrid>
    </VStack>
  );
}
