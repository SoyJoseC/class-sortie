import { useMemo, useState } from 'react';
import {
  Alert,
  AlertIcon,
  Box,
  Button,
  Card,
  CardBody,
  Divider,
  Flex,
  FormControl,
  FormErrorMessage,
  FormHelperText,
  FormLabel,
  Heading,
  HStack,
  Input,
  Radio,
  RadioGroup,
  Select,
  SimpleGrid,
  Stack,
  Text,
  useToast,
  VStack,
} from '@chakra-ui/react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import type { Activity, Classroom, IdentityMode, Question } from '@/api/types';
import {
  useActivityQuery,
  useClassroomsQuery,
  useCreateActivityMutation,
  useLaunchSessionMutation,
  useUpdateActivityMutation,
} from '@/api/caricueApi';
import { errorMessage, fieldErrors } from '@/api/baseQuery';
import { ErrorState, LoadingState } from '@/components/StateViews';
import { QuestionEditor } from '@/components/QuestionEditor';
import { StudentPreview } from '@/components/StudentPreview';
import {
  MAX_QUESTIONS,
  blankQuestion,
  isDraftValid,
  moveQuestion,
  toWritePayload,
  validateDraft,
} from '@/utils/activityDraft';

function numberOrNull(value: string | null): number | null {
  if (!value) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function ActivityBuilderPage() {
  const { id } = useParams<{ id: string }>();
  const isEditing = Boolean(id);

  const classrooms = useClassroomsQuery();
  const existing = useActivityQuery(Number(id), { skip: !isEditing });

  if (isEditing && existing.isLoading) return <LoadingState label="Loading activity…" />;
  if (isEditing && (existing.isError || !existing.data)) {
    return <ErrorState message={errorMessage(existing.error, 'Activity not found.')} />;
  }
  if (classrooms.isLoading) return <LoadingState label="Loading your classes…" />;

  // Both queries have settled, so the editor can take its initial state
  // straight from props instead of syncing it in an effect.
  return (
    <ActivityBuilder
      key={existing.data?.id ?? 'new'}
      activity={isEditing ? existing.data : undefined}
      classrooms={classrooms.data?.results ?? []}
    />
  );
}

function ActivityBuilder({
  activity,
  classrooms,
}: {
  activity?: Activity;
  classrooms: Classroom[];
}) {
  const navigate = useNavigate();
  const toast = useToast();
  const [searchParams] = useSearchParams();

  const [create, createState] = useCreateActivityMutation();
  const [update, updateState] = useUpdateActivityMutation();
  const [launch, launchState] = useLaunchSessionMutation();

  const [title, setTitle] = useState(activity?.title ?? '');
  const [topic, setTopic] = useState(activity?.topic ?? '');
  const [classroom, setClassroom] = useState<number | null>(
    // Preference order: the activity being edited, an explicit ?classroom=
    // link from a class page, then the teacher's only class.
    activity?.classroom ??
      numberOrNull(searchParams.get('classroom')) ??
      (classrooms.length === 1 ? classrooms[0].id : null)
  );
  const [questions, setQuestions] = useState<Question[]>(
    activity?.questions.length ? activity.questions : [blankQuestion()]
  );
  const [identityMode, setIdentityMode] = useState<IdentityMode>('display_name');
  const [showErrors, setShowErrors] = useState(false);

  const isEditing = Boolean(activity);
  const draft = useMemo(() => ({ title, classroom, questions }), [title, classroom, questions]);
  const errors = useMemo(() => validateDraft(draft), [draft]);
  const valid = isDraftValid(errors);

  const mutationError = createState.error ?? updateState.error ?? launchState.error;
  const fields = fieldErrors(mutationError);
  const isSaving = createState.isLoading || updateState.isLoading;

  async function persist(status: 'draft' | 'published') {
    setShowErrors(true);
    if (!valid || classroom === null) return null;
    const body = {
      classroom,
      title: title.trim(),
      topic: topic.trim(),
      status,
      questions: toWritePayload({ title, classroom, questions }),
    };
    if (activity) {
      return update({ id: activity.id, body }).unwrap();
    }
    return create(body).unwrap();
  }

  async function handleSaveDraft() {
    try {
      const saved = await persist('draft');
      if (!saved) return;
      toast({ title: 'Saved as draft', status: 'success', duration: 2500 });
      if (!isEditing) navigate(`/app/activities/${saved.id}`, { replace: true });
    } catch {
      // Rendered below.
    }
  }

  async function handleLaunch() {
    try {
      // Save first so the launched session reflects exactly what is on screen.
      const saved = await persist('draft');
      if (!saved) return;
      const session = await launch({
        activityId: saved.id,
        identity_mode: identityMode,
      }).unwrap();
      navigate(`/app/sessions/${session.id}/launch`);
    } catch {
      // Rendered below.
    }
  }

  return (
    <VStack spacing={5} align="stretch">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap={3}>
        <Box>
          <Heading size="lg">{isEditing ? 'Edit activity' : 'Create an activity'}</Heading>
          <Text color="gray.600">
            One to {MAX_QUESTIONS} questions. Short enough to run in the last five minutes of a
            lesson.
          </Text>
        </Box>
        <HStack flexWrap="wrap">
          {isEditing && activity && (
            <>
              <Button
                as="a"
                href={`/api/activities/${activity.id}/export.csv`}
                download
                variant="ghost"
                size="sm"
              >
                Export CSV
              </Button>
              <Button
                as="a"
                href={`/api/activities/${activity.id}/export.json`}
                download
                variant="ghost"
                size="sm"
              >
                Export JSON
              </Button>
            </>
          )}
          <Button variant="outline" onClick={handleSaveDraft} isLoading={isSaving}>
            Save draft
          </Button>
          <Button
            variant="accent"
            onClick={handleLaunch}
            isLoading={launchState.isLoading || isSaving}
            loadingText="Launching…"
          >
            Launch now
          </Button>
        </HStack>
      </Flex>

      {mutationError && (
        <ErrorState
          title="Could not save this activity"
          message={fields.questions ?? fields.classroom ?? errorMessage(mutationError)}
        />
      )}

      {activity?.follow_up_of_session && (
        <Alert status="info" borderRadius="md">
          <AlertIcon />
          <Box>
            <Text>
              This draft was generated as a follow-up to session{' '}
              {activity.follow_up_of_session_code ?? activity.follow_up_of_session}.
            </Text>
            <Button
              as={Link}
              to={`/app/sessions/${activity.follow_up_of_session}/reflection`}
              size="sm"
              variant="ghost"
              mt={1}
            >
              View source session results
            </Button>
          </Box>
        </Alert>
      )}

      {classrooms.length === 0 && (
        <Alert status="info" borderRadius="md">
          <AlertIcon />
          <Box>
            <Text>You need a class before you can create an activity.</Text>
            <Button
              mt={2}
              size="sm"
              variant="accent"
              onClick={() => navigate('/app/classes/new')}
            >
              Create a class
            </Button>
          </Box>
        </Alert>
      )}

      <SimpleGrid columns={{ base: 1, xl: 3 }} spacing={6}>
        <VStack spacing={5} align="stretch" gridColumn={{ xl: 'span 2' }}>
          <Card borderWidth="1px" borderColor="sand.200">
            <CardBody>
              <VStack spacing={4} align="stretch">
                <FormControl isInvalid={showErrors && Boolean(errors.title)} isRequired>
                  <FormLabel htmlFor="activity-title">Title</FormLabel>
                  <Input
                    id="activity-title"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="Hardware and networking check"
                  />
                  <FormErrorMessage>{errors.title}</FormErrorMessage>
                </FormControl>

                <FormControl>
                  <FormLabel htmlFor="activity-topic">Topic or learning objective</FormLabel>
                  <Input
                    id="activity-topic"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder="Distinguish the role of a switch from a router"
                  />
                  <FormHelperText>
                    Used to label results and to give suggestions context.
                  </FormHelperText>
                </FormControl>

                <FormControl isInvalid={showErrors && Boolean(errors.classroom)} isRequired>
                  <FormLabel htmlFor="activity-classroom">Class</FormLabel>
                  <Select
                    id="activity-classroom"
                    placeholder="Choose a class"
                    value={classroom ?? ''}
                    onChange={(e) =>
                      setClassroom(e.target.value ? Number(e.target.value) : null)
                    }
                  >
                    {classrooms.map((option) => (
                      <option key={option.id} value={option.id}>
                        {option.name} ({option.roster_size} students)
                      </option>
                    ))}
                  </Select>
                  <FormErrorMessage>{errors.classroom}</FormErrorMessage>
                </FormControl>
              </VStack>
            </CardBody>
          </Card>

          <Box>
            <Flex justify="space-between" align="center" mb={3}>
              <Heading size="md">
                Questions ({questions.length}/{MAX_QUESTIONS})
              </Heading>
              <Button
                size="sm"
                variant="outline"
                isDisabled={questions.length >= MAX_QUESTIONS}
                onClick={() => setQuestions([...questions, blankQuestion()])}
              >
                Add question
              </Button>
            </Flex>

            {showErrors && errors.questions && (
              <Alert status="error" borderRadius="md" mb={3}>
                <AlertIcon />
                {errors.questions}
              </Alert>
            )}

            <Stack spacing={4}>
              {questions.map((question, index) => (
                <QuestionEditor
                  key={index}
                  question={question}
                  index={index}
                  total={questions.length}
                  error={showErrors ? errors.byQuestion[index] : undefined}
                  onChange={(next) =>
                    setQuestions(questions.map((q, i) => (i === index ? next : q)))
                  }
                  onRemove={() => setQuestions(questions.filter((_, i) => i !== index))}
                  onMoveUp={() => setQuestions(moveQuestion(questions, index, index - 1))}
                  onMoveDown={() => setQuestions(moveQuestion(questions, index, index + 1))}
                />
              ))}
            </Stack>
          </Box>
        </VStack>

        <VStack spacing={5} align="stretch">
          <Card borderWidth="1px" borderColor="sand.200" position={{ xl: 'sticky' }} top={4}>
            <CardBody>
              <VStack spacing={4} align="stretch">
                <Heading size="sm">How students join</Heading>
                <RadioGroup
                  value={identityMode}
                  onChange={(value) => setIdentityMode(value as IdentityMode)}
                >
                  <Stack spacing={3}>
                    <Radio value="display_name" colorScheme="cariteal">
                      <Box>
                        <Text fontWeight="600">They type a name</Text>
                        <Text fontSize="sm" color="gray.600">
                          Fastest. Works even if the class has no roster.
                        </Text>
                      </Box>
                    </Radio>
                    <Radio value="roster_identifier" colorScheme="cariteal">
                      <Box>
                        <Text fontWeight="600">They enter their roster identifier</Text>
                        <Text fontSize="sm" color="gray.600">
                          Links responses to your roster. Requires school identifiers on
                          students.
                        </Text>
                      </Box>
                    </Radio>
                    <Radio value="google_account" colorScheme="cariteal">
                      <Box>
                        <Text fontWeight="600">School Google account</Text>
                        <Text fontSize="sm" color="gray.600">
                          Students sign in with Google. Their school email must be on the
                          class roster.
                        </Text>
                      </Box>
                    </Radio>
                  </Stack>
                </RadioGroup>

                <Divider />

                <Heading size="sm">Student preview</Heading>
                <Text fontSize="sm" color="gray.600">
                  This is what a student sees. Correct answers are never sent to their device.
                </Text>
                <StudentPreview title={title} topic={topic} questions={questions} />
              </VStack>
            </CardBody>
          </Card>
        </VStack>
      </SimpleGrid>
    </VStack>
  );
}
