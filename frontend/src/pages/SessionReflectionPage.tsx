import { useState } from 'react';
import {
  Alert,
  AlertIcon,
  Box,
  Button,
  Card,
  CardBody,
  Flex,
  FormControl,
  FormErrorMessage,
  FormHelperText,
  FormLabel,
  Heading,
  HStack,
  Radio,
  RadioGroup,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
  useToast,
  VStack,
} from '@chakra-ui/react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import type { MisconceptionCard, PlanImpact, SessionResults } from '@/api/types';
import {
  useCreateReflectionMutation,
  useSessionResultsQuery,
  useUpdateReflectionMutation,
} from '@/api/caricueApi';
import { errorMessage, fieldErrors } from '@/api/baseQuery';
import { ErrorState, LoadingState } from '@/components/StateViews';
import { StatTile } from '@/components/StatTile';
import { FactBadge } from '@/components/FactBadge';
import { MisconceptionCardPanel } from '@/components/MisconceptionCardPanel';
import { SessionComparisonPanel } from '@/components/SessionComparisonPanel';
import {
  formatCompletion,
  formatConfidence,
  formatPercent,
  formatDateTime,
} from '@/utils/insightFormat';

const IMPACT_OPTIONS: { value: PlanImpact; label: string; help: string }[] = [
  {
    value: 'confirmed',
    label: 'Confirmed my plan',
    help: 'The class is where I expected. I will carry on as planned.',
  },
  {
    value: 'changed',
    label: 'Changed my plan',
    help: 'I will reteach, reorder, or slow down because of what I saw.',
  },
  {
    value: 'unclear',
    label: 'Still unclear',
    help: 'Not enough evidence yet. I need another check.',
  },
];

/**
 * The last step of the loop, and the reason the product exists: turning
 * evidence into a stated instructional decision.
 */
export function SessionReflectionPage() {
  const { id } = useParams<{ id: string }>();
  const sessionId = Number(id);

  const { data, isLoading, isError, error, refetch } = useSessionResultsQuery(sessionId);

  if (isLoading) return <LoadingState label="Loading session results…" />;
  if (isError || !data) {
    return (
      <ErrorState
        message={errorMessage(error, 'Could not load this session.')}
        onRetry={() => void refetch()}
      />
    );
  }

  // Keying on the reflection means editing an existing one starts from the
  // saved values without an effect copying them into state.
  return (
    <ReflectionForm key={data.reflection?.id ?? 'new'} sessionId={sessionId} results={data} />
  );
}

function ReflectionForm({
  sessionId,
  results,
}: {
  sessionId: number;
  results: SessionResults;
}) {
  const navigate = useNavigate();
  const toast = useToast();
  const { session, facts, suggestions, reflection, misconception_cards, comparison } =
    results;

  const [create, createState] = useCreateReflectionMutation();
  const [update, updateState] = useUpdateReflectionMutation();

  const baselineGap = comparison?.baseline_snapshot?.primary_gap ?? '';

  const [primaryGap, setPrimaryGap] = useState(
    reflection?.primary_gap || baselineGap
  );
  const [planImpact, setPlanImpact] = useState<PlanImpact>(
    reflection?.plan_impact ?? 'confirmed'
  );
  const [plannedAction, setPlannedAction] = useState(reflection?.planned_action ?? '');
  const [notes, setNotes] = useState(reflection?.notes ?? '');
  const [showErrors, setShowErrors] = useState(false);

  const mutationError = createState.error ?? updateState.error;
  const fields = fieldErrors(mutationError);
  const isSaving = createState.isLoading || updateState.isLoading;

  // "Still unclear" is a legitimate outcome, so an action is only required
  // when the teacher says the evidence confirmed or changed the plan.
  const actionRequired = planImpact !== 'unclear';
  const gapError = primaryGap.trim().length < 3 ? 'Describe the gap in a few words.' : '';
  const actionError =
    actionRequired && plannedAction.trim().length < 3
      ? 'Say what you will do next lesson.'
      : '';
  const canSubmit = !gapError && !actionError;

  function handleUseCardInReflection(card: MisconceptionCard) {
    if (card.suggestion) {
      setPrimaryGap((current) => current || card.suggestion!.title);
      setPlannedAction((current) =>
        current ? `${current}\n${card.suggestion!.body}` : card.suggestion!.body
      );
      setPlanImpact('changed');
    }
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setShowErrors(true);
    if (!canSubmit) return;

    const body = {
      primary_gap: primaryGap.trim(),
      plan_impact: planImpact,
      planned_action: plannedAction.trim(),
      notes: notes.trim(),
    };

    try {
      if (reflection) {
        await update({ id: reflection.id, live_session: sessionId, body }).unwrap();
        toast({ title: 'Reflection updated', status: 'success', duration: 2500 });
      } else {
        await create({ live_session: sessionId, ...body }).unwrap();
        toast({
          title: 'Reflection saved',
          description: 'The evidence and your decision are now recorded together.',
          status: 'success',
        });
      }
      navigate('/app');
    } catch {
      // Rendered below.
    }
  }

  return (
    <VStack spacing={5} align="stretch">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap={3}>
        <Box>
          <Heading size="lg">What will you do next?</Heading>
          <Text color="gray.600">
            {session.activity_title} · {session.classroom_name} · closed{' '}
            {formatDateTime(session.closed_at)}
          </Text>
        </Box>
        <Button
          as={Link}
          to={`/app/sessions/${sessionId}/submissions`}
          variant="outline"
          size="sm"
        >
          View submissions
        </Button>
      </Flex>

      {session.status === 'open' && (
        <Alert status="warning" borderRadius="md">
          <AlertIcon />
          <Box>
            <Text>
              This session is still open, so the numbers below may change. You can record a
              reflection now and edit it later.
            </Text>
            <Button
              as={Link}
              to={`/app/sessions/${sessionId}`}
              size="sm"
              variant="ghost"
              mt={1}
            >
              Back to live results
            </Button>
          </Box>
        </Alert>
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
          accent="cariteal"
        />
        <StatTile
          label="Auto-scored correct"
          value={formatPercent(facts.overall_correctness_percentage)}
          accent="coral"
        />
        <StatTile
          label="Average confidence"
          value={formatConfidence(facts.average_confidence)}
          accent="gray"
        />
      </SimpleGrid>

      {comparison && (
        <SessionComparisonPanel comparison={comparison} classroomId={session.classroom} />
      )}

      {(misconception_cards?.length ?? 0) > 0 && (
        <MisconceptionCardPanel
          sessionId={sessionId}
          cards={misconception_cards ?? []}
          showBulkFollowUp
          actions={{ onUseInReflection: handleUseCardInReflection }}
        />
      )}

      <SimpleGrid columns={{ base: 1, lg: 3 }} spacing={5}>
        <Box gridColumn={{ lg: 'span 2' }}>
          <Card borderWidth="1px" borderColor="sand.200" as="form" onSubmit={handleSubmit}>
            <CardBody>
              <VStack spacing={5} align="stretch">
                {mutationError && (
                  <ErrorState
                    title="Could not save this reflection"
                    message={
                      fields.primary_gap ??
                      fields.planned_action ??
                      fields.live_session ??
                      errorMessage(mutationError)
                    }
                  />
                )}

                <FormControl isInvalid={showErrors && Boolean(gapError)} isRequired>
                  <FormLabel htmlFor="primary-gap">The main gap you saw</FormLabel>
                  <Textarea
                    id="primary-gap"
                    value={primaryGap}
                    onChange={(e) => setPrimaryGap(e.target.value)}
                    placeholder="Most students still treat a switch and a router as interchangeable."
                    rows={3}
                  />
                  <FormErrorMessage>{gapError}</FormErrorMessage>
                </FormControl>

                <FormControl isRequired>
                  <FormLabel>Did this change your lesson plan?</FormLabel>
                  <RadioGroup
                    value={planImpact}
                    onChange={(value) => setPlanImpact(value as PlanImpact)}
                  >
                    <Stack spacing={3}>
                      {IMPACT_OPTIONS.map((option) => (
                        <Radio key={option.value} value={option.value} colorScheme="cariteal">
                          <Box>
                            <Text fontWeight="600">{option.label}</Text>
                            <Text fontSize="sm" color="gray.600">
                              {option.help}
                            </Text>
                          </Box>
                        </Radio>
                      ))}
                    </Stack>
                  </RadioGroup>
                </FormControl>

                <FormControl
                  isInvalid={showErrors && Boolean(actionError)}
                  isRequired={actionRequired}
                >
                  <FormLabel htmlFor="planned-action">
                    What you will review, reteach, or reinforce
                  </FormLabel>
                  <Textarea
                    id="planned-action"
                    value={plannedAction}
                    onChange={(e) => setPlannedAction(e.target.value)}
                    placeholder="Open next lesson with a five-minute switch-versus-router comparison, then re-check with three questions."
                    rows={3}
                  />
                  <FormErrorMessage>{actionError}</FormErrorMessage>
                  {!actionError && (
                    <FormHelperText>
                      {actionRequired
                        ? 'Concrete enough that you could act on it next lesson.'
                        : 'Optional while the evidence is still unclear.'}
                    </FormHelperText>
                  )}
                </FormControl>

                <FormControl>
                  <FormLabel htmlFor="reflection-notes">Notes (optional)</FormLabel>
                  <Textarea
                    id="reflection-notes"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Anything you want to remember about how the class went."
                    rows={2}
                  />
                </FormControl>

                <Flex justify="flex-end" gap={3}>
                  <Button as={Link} to={`/app/sessions/${sessionId}`} variant="ghost">
                    Back to results
                  </Button>
                  <Button
                    type="submit"
                    variant="accent"
                    isLoading={isSaving}
                    loadingText="Saving…"
                  >
                    {reflection ? 'Update reflection' : 'Save reflection'}
                  </Button>
                </Flex>
              </VStack>
            </CardBody>
          </Card>
        </Box>

        <VStack spacing={4} align="stretch">
          <Card borderWidth="1px" borderColor="sand.200">
            <CardBody>
              <HStack justify="space-between" mb={2}>
                <Heading size="sm" color="ocean.800">
                  What the responses showed
                </Heading>
                <FactBadge />
              </HStack>
              {facts.lowest_correctness_questions.length === 0 ? (
                <Text fontSize="sm" color="gray.600">
                  No auto-scored questions to rank.
                </Text>
              ) : (
                <VStack align="stretch" spacing={2}>
                  {facts.lowest_correctness_questions.map((item) => (
                    <Box key={item.question_id} bg="sand.100" px={3} py={2} borderRadius="md">
                      <Text fontSize="sm" fontWeight="600">
                        Q{item.position} · {formatPercent(item.correctness_percentage)} correct
                      </Text>
                      <Text fontSize="sm" color="gray.700">
                        {item.prompt}
                      </Text>
                    </Box>
                  ))}
                </VStack>
              )}
              {facts.high_confidence_incorrect.length > 0 && (
                <Text fontSize="sm" color="coral.700" mt={3}>
                  {facts.high_confidence_incorrect.length} confident but incorrect answer
                  {facts.high_confidence_incorrect.length === 1 ? '' : 's'} — often the clearest
                  sign of a misconception.
                </Text>
              )}
            </CardBody>
          </Card>

          {suggestions.length > 0 && (
            <Card borderWidth="1px" borderColor="coral.200" bg="coral.50">
              <CardBody>
                <Heading size="sm" color="ocean.800" mb={2}>
                  Suggestions to consider
                </Heading>
                <VStack align="stretch" spacing={2}>
                  {suggestions.slice(0, 3).map((suggestion, index) => (
                    <Box
                      key={index}
                      bg="white"
                      borderWidth="1px"
                      borderColor="coral.200"
                      borderRadius="md"
                      p={3}
                    >
                      <Text fontWeight="700" fontSize="sm" color="ocean.800">
                        {suggestion.title}
                      </Text>
                      <Text fontSize="sm" color="gray.700">
                        {suggestion.body}
                      </Text>
                      <Button
                        size="xs"
                        variant="ghost"
                        mt={2}
                        onClick={() =>
                          setPlannedAction((current) =>
                            current ? `${current}\n${suggestion.body}` : suggestion.body
                          )
                        }
                      >
                        Use as a starting point
                      </Button>
                    </Box>
                  ))}
                </VStack>
                <Text fontSize="xs" color="gray.600" mt={2}>
                  Suggestions never save themselves. Copying one into the box is your decision.
                </Text>
              </CardBody>
            </Card>
          )}
        </VStack>
      </SimpleGrid>
    </VStack>
  );
}
