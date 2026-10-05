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
  VStack,
} from '@chakra-ui/react';
import { Link, useParams } from 'react-router-dom';
import {
  caricueApi,
  useSessionDashboardQuery,
} from '@/api/caricueApi';
import { errorMessage } from '@/api/baseQuery';
import { AnonymousClassSignals } from '@/components/AnonymousClassSignals';
import { ConfidenceChart } from '@/components/ConfidenceChart';
import { ErrorState, LoadingState } from '@/components/StateViews';
import { FactBadge } from '@/components/FactBadge';
import { MisconceptionCardPanel } from '@/components/MisconceptionCardPanel';
import { QuestionInsightCard } from '@/components/QuestionInsightCard';
import { StatTile } from '@/components/StatTile';
import { SuggestionPanel } from '@/components/SuggestionPanel';
import {
  formatCompletion,
  formatConfidence,
  formatPercent,
  formatRelativeTime,
} from '@/utils/insightFormat';

const DEFAULT_POLL_SECONDS = 4;

/**
 * Aggregate session results for whole-class discussion.
 *
 * Uses the same dashboard data as the live view but never shows student names,
 * individual attention lists, or per-student comparison movement.
 */
export function SessionDiscussPage() {
  const { id } = useParams<{ id: string }>();
  const sessionId = Number(id);
  const [autoRefreshWanted, setAutoRefreshWanted] = useState(true);

  const cached = caricueApi.endpoints.sessionDashboard.useQueryState(sessionId);
  const pollSeconds = cached.data?.poll_interval_seconds ?? DEFAULT_POLL_SECONDS;
  const sessionIsOpen = cached.data?.session.status !== 'closed';
  const autoRefresh = autoRefreshWanted && sessionIsOpen;

  const { data, isLoading, isError, error, isFetching, refetch, fulfilledTimeStamp } =
    useSessionDashboardQuery(sessionId, {
      pollingInterval: autoRefresh ? pollSeconds * 1000 : 0,
      refetchOnMountOrArgChange: true,
    });

  const lastUpdated = fulfilledTimeStamp ? new Date(fulfilledTimeStamp).toISOString() : null;

  if (isLoading) return <LoadingState label="Loading class results…" />;
  if (isError || !data) {
    return (
      <ErrorState
        message={errorMessage(error, 'Could not load this session.')}
        onRetry={() => void refetch()}
      />
    );
  }

  const { session, facts, suggestions, misconception_cards } = data;

  return (
    <VStack spacing={5} align="stretch">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap={3}>
        <Box>
          <HStack spacing={2} mb={1}>
            <Heading size="lg">Discuss in class</Heading>
            <Badge colorScheme="ocean" variant="subtle">
              Anonymous
            </Badge>
          </HStack>
          <Text color="gray.600">
            {session.activity_title}
            {session.activity_topic ? ` · ${session.activity_topic}` : ''}
          </Text>
          <Text fontSize="sm" color="gray.600" mt={1}>
            Safe to project: no student names or individual submissions appear here.
          </Text>
        </Box>
        <HStack wrap="wrap">
          <Button as={Link} to={`/app/sessions/${sessionId}`} variant="outline" size="sm">
            Live results (teacher view)
          </Button>
          <Button
            as={Link}
            to={`/app/sessions/${sessionId}/launch`}
            variant="ghost"
            size="sm"
          >
            Show code
          </Button>
        </HStack>
      </Flex>

      <Alert status="info" borderRadius="md" variant="left-accent">
        <AlertIcon />
        <Text fontSize="sm">
          For named submissions and follow-up with individuals, use{' '}
          <Link to={`/app/sessions/${sessionId}/submissions`} style={{ fontWeight: 600 }}>
            Submissions
          </Link>{' '}
          or live results — not this screen.
        </Text>
      </Alert>

      {sessionIsOpen && (
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
              id="discuss-auto-refresh"
              isChecked={autoRefresh}
              onChange={(e) => setAutoRefreshWanted(e.target.checked)}
              colorScheme="cariteal"
            />
            <Text as="label" htmlFor="discuss-auto-refresh" fontSize="sm" color="gray.700">
              Auto-refresh every {pollSeconds}s
            </Text>
          </HStack>
          <HStack spacing={3}>
            <Text fontSize="sm" color="gray.600" aria-live="polite">
              {isFetching ? 'Updating…' : `Updated ${formatRelativeTime(lastUpdated)}`}
            </Text>
            <Button size="xs" variant="ghost" onClick={() => void refetch()} isLoading={isFetching}>
              Refresh now
            </Button>
          </HStack>
        </Flex>
      )}

      <SimpleGrid columns={{ base: 1, sm: 2, lg: 4 }} spacing={4}>
        <StatTile
          label="Submitted"
          value={String(facts.submitted_count)}
          help={formatCompletion(facts)}
        />
        <StatTile
          label="Completion"
          value={formatPercent(facts.completion_percentage)}
          help={
            facts.roster_size > 0
              ? `Roster of ${facts.roster_size}`
              : 'No roster size on file'
          }
          accent="cariteal"
        />
        <StatTile
          label="Auto-scored correct"
          value={formatPercent(facts.overall_correctness_percentage)}
          help={
            facts.has_auto_scored_data
              ? `${facts.auto_scored_response_count} scored answers`
              : 'No auto-scored answers yet'
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
            {facts.submitted_count === 0 ? (
              <Text color="gray.600" fontSize="sm">
                Waiting for the first submission…
              </Text>
            ) : (
              <VStack spacing={4} align="stretch">
                {facts.questions.map((question) => (
                  <QuestionInsightCard key={question.question_id} question={question} />
                ))}
              </VStack>
            )}
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

          <AnonymousClassSignals facts={facts} />

          {facts.submitted_count > 0 && misconception_cards && misconception_cards.length > 0 && (
            <MisconceptionCardPanel sessionId={sessionId} cards={misconception_cards} />
          )}

          <SuggestionPanel suggestions={suggestions} />
        </VStack>
      </SimpleGrid>
    </VStack>
  );
}
