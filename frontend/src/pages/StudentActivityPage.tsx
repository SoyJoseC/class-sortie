import { useEffect, useState } from 'react';
import {
  Alert,
  AlertIcon,
  Badge,
  Box,
  Button,
  Card,
  CardBody,
  FormControl,
  FormErrorMessage,
  FormHelperText,
  FormLabel,
  Heading,
  HStack,
  Input,
  Progress,
  Radio,
  RadioGroup,
  Stack,
  Text,
  Textarea,
  VStack,
} from '@chakra-ui/react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import type { PublicAnswer, PublicQuestion, PublicSession } from '@/api/types';
import {
  useJoinSessionMutation,
  usePublicSessionQuery,
  useStudentMeQuery,
  useSubmitAnswersMutation,
} from '@/api/caricueApi';
import { googleLoginUrl, oauthErrorMessage } from '@/utils/googleAuth';
import { errorMessage } from '@/api/baseQuery';
import { ErrorState, LoadingState } from '@/components/StateViews';
import { StudentShell } from '@/components/StudentShell';
import { ConfidenceScale } from '@/components/ConfidenceScale';

type Phase = 'identify' | 'answer' | 'done';

interface DraftAnswer {
  selected_choice?: number;
  text_response?: string;
  confidence_value?: number;
}

/**
 * The whole student experience: identify, answer, submit once, confirm.
 *
 * Reached by the unguessable public token, never by the short code, so a
 * shared link cannot be walked back to other sessions.
 */
export function StudentActivityPage() {
  const { token = '' } = useParams<{ token: string }>();
  const [searchParams] = useSearchParams();
  const oauthError = oauthErrorMessage(searchParams.get('oauth_error'));
  const session = usePublicSessionQuery(token);

  const [phase, setPhase] = useState<Phase>('identify');
  const [identifier, setIdentifier] = useState('');
  const [participantToken, setParticipantToken] = useState('');
  const [label, setLabel] = useState('');
  const [answers, setAnswers] = useState<Record<number, DraftAnswer>>({});
  const [submittedAt, setSubmittedAt] = useState('');
  const [answerCount, setAnswerCount] = useState(0);
  const [showErrors, setShowErrors] = useState(false);

  const [join, joinState] = useJoinSessionMutation();
  const [submit, submitState] = useSubmitAnswersMutation();

  const googleMode = session.data?.identity_mode === 'google_account';
  const studentMe = useStudentMeQuery(undefined, { skip: !googleMode });

  useEffect(() => {
    if (!googleMode || phase !== 'identify' || !studentMe.data || joinState.isLoading) {
      return;
    }
    void join({ token })
      .unwrap()
      .then((result) => {
        setParticipantToken(result.participant_token);
        setLabel(result.display_label);
        setShowErrors(false);
        setPhase('answer');
      })
      .catch(() => {
        // Rendered inline.
      });
  }, [googleMode, phase, studentMe.data, joinState.isLoading, join, token]);

  if (session.isLoading) return <LoadingState label="Loading activity…" />;
  if (session.isError || !session.data) {
    return (
      <StudentShell>
        <ErrorState
          title="Activity not found"
          message={errorMessage(
            session.error,
            'This link is not valid. Ask your teacher for the code again.'
          )}
        />
        <Button as={Link} to="/join" variant="outline">
          Enter a code instead
        </Button>
      </StudentShell>
    );
  }

  const data = session.data;
  const roster = data.identity_mode === 'roster_identifier';

  if (phase === 'done') {
    return (
      <ConfirmationView
        session={data}
        label={label}
        submittedAt={submittedAt}
        answerCount={answerCount}
      />
    );
  }

  if (!data.is_open) {
    return (
      <StudentShell subtitle={data.class_name}>
        <Alert
          status="warning"
          borderRadius="md"
          flexDirection="column"
          alignItems="flex-start"
        >
          <HStack>
            <AlertIcon />
            <Text fontWeight="700">This activity is closed</Text>
          </HStack>
          <Text mt={2} fontSize="sm">
            Your teacher has stopped collecting answers for “{data.activity_title}”.
          </Text>
        </Alert>
      </StudentShell>
    );
  }

  async function handleJoin(event: React.FormEvent) {
    event.preventDefault();
    setShowErrors(true);
    if (!googleMode && !identifier.trim()) return;
    try {
      const result = await join(
        googleMode ? { token } : { token, identifier: identifier.trim() }
      ).unwrap();
      setParticipantToken(result.participant_token);
      setLabel(result.display_label);
      setShowErrors(false);
      setPhase('answer');
    } catch {
      // Rendered below.
    }
  }

  function setAnswer(questionId: number, patch: DraftAnswer) {
    setAnswers((current) => ({
      ...current,
      [questionId]: { ...current[questionId], ...patch },
    }));
  }

  function isAnswered(question: PublicQuestion): boolean {
    const answer = answers[question.id];
    if (!answer) return false;
    if (question.question_type === 'multiple_choice')
      return answer.selected_choice !== undefined;
    if (question.question_type === 'short_text') return Boolean(answer.text_response?.trim());
    return answer.confidence_value !== undefined;
  }

  function missingConfidence(question: PublicQuestion): boolean {
    if (question.question_type === 'confidence') return false;
    if (!question.collect_confidence) return false;
    // Only nag for confidence once the question itself has an answer.
    return isAnswered(question) && answers[question.id]?.confidence_value === undefined;
  }

  const unanswered = data.questions.filter(
    (question) => question.is_required && !isAnswered(question)
  );
  const incompleteConfidence = data.questions.filter(missingConfidence);
  const canSubmit = unanswered.length === 0 && incompleteConfidence.length === 0;
  const answeredCount = data.questions.filter(isAnswered).length;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setShowErrors(true);
    if (!canSubmit) return;

    const payload: PublicAnswer[] = data.questions.filter(isAnswered).map((question) => {
      const answer = answers[question.id];
      return {
        question: question.id,
        ...(answer.selected_choice !== undefined
          ? { selected_choice: answer.selected_choice }
          : {}),
        ...(answer.text_response ? { text_response: answer.text_response.trim() } : {}),
        ...(answer.confidence_value !== undefined
          ? { confidence_value: answer.confidence_value }
          : {}),
      };
    });

    try {
      const result = await submit({
        token,
        participant_token: participantToken,
        answers: payload,
      }).unwrap();
      setSubmittedAt(result.submitted_at);
      setAnswerCount(result.answer_count);
      setPhase('done');
    } catch {
      // Rendered below.
    }
  }

  if (phase === 'identify') {
    const nextUrl = `/s/${token}`;

    return (
      <StudentShell subtitle={data.class_name} googleAccountMode={googleMode}>
        <Box>
          <Heading size="md" color="ocean.800">
            {data.activity_title}
          </Heading>
          {data.activity_topic && (
            <Text fontSize="sm" color="cariteal.700">
              {data.activity_topic}
            </Text>
          )}
          <Text fontSize="sm" color="gray.600" mt={1}>
            {data.questions.length} question{data.questions.length === 1 ? '' : 's'} · code{' '}
            {data.code}
          </Text>
        </Box>

        {oauthError && (
          <Alert status="error" borderRadius="md">
            <AlertIcon />
            <Text fontSize="sm">{oauthError}</Text>
          </Alert>
        )}

        {googleMode ? (
          <Card borderWidth="1px" borderColor="sand.200">
            <CardBody>
              {studentMe.data ? (
                <VStack align="stretch" spacing={4}>
                  <FormControl>
                    <FormLabel>Signed in as</FormLabel>
                    <Text fontWeight="600">{studentMe.data.full_name}</Text>
                    <Text fontSize="sm" color="gray.600">
                      {studentMe.data.email}
                    </Text>
                  </FormControl>
                  {joinState.error && (
                    <FormErrorMessage display="block">
                      {errorMessage(
                        joinState.error,
                        'Could not join. Check with your teacher.'
                      )}
                    </FormErrorMessage>
                  )}
                  <Button
                    variant="accent"
                    size="lg"
                    w="full"
                    isLoading={joinState.isLoading}
                    loadingText="Joining…"
                    onClick={() => void handleJoin({ preventDefault: () => undefined } as React.FormEvent)}
                  >
                    Start
                  </Button>
                </VStack>
              ) : (
                <VStack align="stretch" spacing={4}>
                  <Text fontSize="sm" color="gray.600">
                    Sign in with your school Google account. Your teacher matches you to the
                    class roster by email.
                  </Text>
                  <Button
                    as="a"
                    href={googleLoginUrl('student', nextUrl)}
                    variant="accent"
                    size="lg"
                    w="full"
                  >
                    Sign in with Google
                  </Button>
                </VStack>
              )}
            </CardBody>
          </Card>
        ) : (
        <Card as="form" onSubmit={handleJoin} borderWidth="1px" borderColor="sand.200">
          <CardBody>
            <FormControl
              isInvalid={(showErrors && !identifier.trim()) || Boolean(joinState.error)}
              isRequired
            >
              <FormLabel htmlFor="student-identifier">
                {roster ? 'Your roster identifier' : 'Your name'}
              </FormLabel>
              <Input
                id="student-identifier"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder={roster ? 'e.g. 2024-0431' : 'e.g. Amara J.'}
                size="lg"
                autoComplete={roster ? 'off' : 'name'}
                enterKeyHint="go"
                maxLength={80}
              />
              <FormErrorMessage>
                {joinState.error
                  ? errorMessage(joinState.error, 'Could not join. Check with your teacher.')
                  : 'Please enter something so your teacher knows who answered.'}
              </FormErrorMessage>
              {!joinState.error && (
                <FormHelperText>
                  {roster
                    ? 'The identifier your teacher gave you. Nothing else is needed.'
                    : 'Your teacher will see this next to your answers.'}
                </FormHelperText>
              )}
            </FormControl>

            <Button
              type="submit"
              variant="accent"
              size="lg"
              w="full"
              mt={5}
              isLoading={joinState.isLoading}
              loadingText="Joining…"
            >
              Start
            </Button>
          </CardBody>
        </Card>
        )}
      </StudentShell>
    );
  }

  return (
    <StudentShell subtitle={`${data.activity_title} · ${label}`}>
      <Box>
        <Progress
          value={(answeredCount / Math.max(data.questions.length, 1)) * 100}
          size="sm"
          colorScheme="cariteal"
          borderRadius="full"
          aria-label="Questions answered"
        />
        <Text fontSize="xs" color="gray.600" mt={1} aria-live="polite">
          {answeredCount} of {data.questions.length} answered
        </Text>
      </Box>

      {submitState.error && (
        <ErrorState
          title="Could not submit"
          message={errorMessage(submitState.error, 'Please try again.')}
        />
      )}

      <VStack as="form" onSubmit={handleSubmit} align="stretch" spacing={4}>
        {data.questions.map((question, index) => {
          const answer = answers[question.id] ?? {};
          const isMissing = showErrors && question.is_required && !isAnswered(question);
          const needsConfidence = showErrors && missingConfidence(question);

          return (
            <Card
              key={question.id}
              borderWidth="1px"
              borderColor={isMissing || needsConfidence ? 'coral.400' : 'sand.200'}
            >
              <CardBody>
                <VStack align="stretch" spacing={3}>
                  <Box>
                    <HStack spacing={2} mb={1}>
                      <Badge colorScheme="ocean" variant="subtle">
                        {index + 1} of {data.questions.length}
                      </Badge>
                      {!question.is_required && (
                        <Badge colorScheme="gray" variant="subtle">
                          optional
                        </Badge>
                      )}
                    </HStack>
                    {/* Labels its inputs via aria-labelledby, so the prompt
                        is announced once rather than twice. */}
                    <Text
                      id={`prompt-${question.id}`}
                      fontWeight="700"
                      color="ocean.800"
                      fontSize="lg"
                    >
                      {question.prompt}
                    </Text>
                  </Box>

                  {question.question_type === 'multiple_choice' && (
                    <FormControl isInvalid={isMissing}>
                      <RadioGroup
                        value={
                          answer.selected_choice !== undefined
                            ? String(answer.selected_choice)
                            : ''
                        }
                        onChange={(value) =>
                          setAnswer(question.id, { selected_choice: Number(value) })
                        }
                        role="radiogroup"
                        aria-labelledby={`prompt-${question.id}`}
                      >
                        <Stack spacing={2}>
                          {question.choices.map((choice) => (
                            <Box
                              key={choice.id}
                              borderWidth="1px"
                              borderColor={
                                answer.selected_choice === choice.id
                                  ? 'cariteal.500'
                                  : 'sand.200'
                              }
                              bg={
                                answer.selected_choice === choice.id ? 'cariteal.50' : 'white'
                              }
                              borderRadius="md"
                              px={3}
                              py={3}
                            >
                              <Radio value={String(choice.id)} colorScheme="cariteal" w="full">
                                <Text fontSize="md">{choice.text}</Text>
                              </Radio>
                            </Box>
                          ))}
                        </Stack>
                      </RadioGroup>
                      <FormErrorMessage>Please choose an answer.</FormErrorMessage>
                    </FormControl>
                  )}

                  {question.question_type === 'short_text' && (
                    <FormControl isInvalid={isMissing}>
                      <Textarea
                        id={`answer-${question.id}`}
                        aria-labelledby={`prompt-${question.id}`}
                        value={answer.text_response ?? ''}
                        onChange={(e) =>
                          setAnswer(question.id, { text_response: e.target.value })
                        }
                        placeholder="Type your answer"
                        size="lg"
                        rows={4}
                        maxLength={1000}
                        resize="vertical"
                      />
                      <FormErrorMessage>Please write an answer.</FormErrorMessage>
                    </FormControl>
                  )}

                  {question.question_type === 'confidence' && (
                    <FormControl isInvalid={isMissing}>
                      <ConfidenceScale
                        name={`confidence-${question.id}`}
                        legend="Choose a number from 1 to 5."
                        value={answer.confidence_value}
                        onChange={(value) =>
                          setAnswer(question.id, { confidence_value: value })
                        }
                        scale={data.confidence_scale}
                      />
                      <FormErrorMessage>Please pick a number.</FormErrorMessage>
                    </FormControl>
                  )}

                  {question.question_type !== 'confidence' && question.collect_confidence && (
                    <FormControl isInvalid={needsConfidence}>
                      <ConfidenceScale
                        name={`confidence-${question.id}`}
                        legend="How sure are you about that answer?"
                        value={answer.confidence_value}
                        onChange={(value) =>
                          setAnswer(question.id, { confidence_value: value })
                        }
                        scale={data.confidence_scale}
                      />
                      <FormErrorMessage>Pick a rating from 1 to 5.</FormErrorMessage>
                    </FormControl>
                  )}
                </VStack>
              </CardBody>
            </Card>
          );
        })}

        {showErrors && !canSubmit && (
          <Alert status="error" borderRadius="md" fontSize="sm">
            <AlertIcon />
            {unanswered.length > 0
              ? `Please answer question ${unanswered
                  .map((question) => question.position)
                  .join(', ')}.`
              : 'Please say how sure you are for each answer.'}
          </Alert>
        )}

        <Button
          type="submit"
          variant="accent"
          size="lg"
          isLoading={submitState.isLoading}
          loadingText="Sending…"
        >
          Submit answers
        </Button>
        <Text fontSize="xs" color="gray.600" textAlign="center">
          You can only submit once. Check your answers first.
        </Text>
      </VStack>
    </StudentShell>
  );
}

function ConfirmationView({
  session,
  label,
  submittedAt,
  answerCount,
}: {
  session: PublicSession;
  label: string;
  submittedAt: string;
  answerCount: number;
}) {
  const time = submittedAt ? new Date(submittedAt).toLocaleTimeString() : '';

  return (
    <StudentShell subtitle={session.class_name}>
      <Card borderWidth="1px" borderColor="cariteal.300" bg="cariteal.50">
        <CardBody>
          <VStack spacing={3} align="center" textAlign="center" py={4}>
            <Box
              w="56px"
              h="56px"
              borderRadius="full"
              bg="cariteal.600"
              color="white"
              display="flex"
              alignItems="center"
              justifyContent="center"
              fontSize="2xl"
              aria-hidden="true"
            >
              ✓
            </Box>
            <Heading size="md" color="ocean.800">
              Answers sent
            </Heading>
            <Text color="gray.700">
              Thanks{label ? `, ${label}` : ''}. Your teacher has your {answerCount} answer
              {answerCount === 1 ? '' : 's'} for “{session.activity_title}”.
            </Text>
            {time && (
              <Text fontSize="sm" color="gray.600">
                Submitted at {time}
              </Text>
            )}
          </VStack>
        </CardBody>
      </Card>

      <Text fontSize="sm" color="gray.700" textAlign="center">
        You can close this page. There is nothing else to do.
      </Text>
    </StudentShell>
  );
}
