import { useState } from 'react';
import {
  Button,
  Card,
  CardBody,
  FormControl,
  FormErrorMessage,
  FormLabel,
  Heading,
  HStack,
  Input,
  Switch,
  Text,
  VStack,
} from '@chakra-ui/react';
import { useNavigate, useParams } from 'react-router-dom';
import type { Classroom } from '@/api/types';
import {
  useClassroomQuery,
  useCreateClassroomMutation,
  useUpdateClassroomMutation,
} from '@/api/caricueApi';
import { errorMessage, fieldErrors } from '@/api/baseQuery';
import { ErrorState, LoadingState } from '@/components/StateViews';

/**
 * Create or edit a class. Same form either way; `id` decides the mode.
 *
 * The fetch is separated from the form so the form's initial state comes from
 * props rather than from an effect that mirrors the response into state.
 */
export function ClassFormPage() {
  const { id } = useParams<{ id: string }>();
  const isEditing = Boolean(id);

  const existing = useClassroomQuery(Number(id), { skip: !isEditing });

  if (isEditing && existing.isLoading) return <LoadingState label="Loading class…" />;
  if (isEditing && (existing.isError || !existing.data)) {
    return <ErrorState message={errorMessage(existing.error, 'Class not found.')} />;
  }

  return <ClassForm classroom={isEditing ? existing.data : undefined} />;
}

function ClassForm({ classroom }: { classroom?: Classroom }) {
  const navigate = useNavigate();
  const isEditing = Boolean(classroom);

  const [create, createState] = useCreateClassroomMutation();
  const [update, updateState] = useUpdateClassroomMutation();

  const [name, setName] = useState(classroom?.name ?? '');
  const [subject, setSubject] = useState(classroom?.subject ?? '');
  const [level, setLevel] = useState(classroom?.level ?? '');
  const [academicPeriod, setAcademicPeriod] = useState(classroom?.academic_period ?? '');
  const [isActive, setIsActive] = useState(classroom?.is_active ?? true);
  const [touched, setTouched] = useState(false);

  const mutationError = createState.error ?? updateState.error;
  const fields = fieldErrors(mutationError);
  const isSaving = createState.isLoading || updateState.isLoading;
  const nameProblem = touched && !name.trim() ? 'Give the class a name.' : fields.name;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (!name.trim()) return;

    const body = {
      name: name.trim(),
      subject: subject.trim(),
      level: level.trim(),
      academic_period: academicPeriod.trim(),
      is_active: isActive,
    };

    try {
      if (classroom) {
        await update({ id: classroom.id, body }).unwrap();
        navigate(`/app/classes/${classroom.id}`);
      } else {
        const created = await create(body).unwrap();
        navigate(`/app/classes/${created.id}`);
      }
    } catch {
      // Rendered from the mutation error below.
    }
  }

  return (
    <VStack spacing={5} align="stretch" maxW="2xl">
      <Heading size="lg">{isEditing ? 'Edit class' : 'Create a class'}</Heading>

      <Card borderWidth="1px" borderColor="sand.200">
        <CardBody>
          <VStack as="form" spacing={4} align="stretch" onSubmit={handleSubmit} noValidate>
            {mutationError && !Object.keys(fields).length && (
              <ErrorState message={errorMessage(mutationError)} />
            )}

            <FormControl isInvalid={Boolean(nameProblem)} isRequired>
              <FormLabel htmlFor="class-name">Class name</FormLabel>
              <Input
                id="class-name"
                name="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Form 4 Information Technology"
              />
              <FormErrorMessage>{nameProblem}</FormErrorMessage>
            </FormControl>

            <FormControl isInvalid={Boolean(fields.subject)}>
              <FormLabel htmlFor="class-subject">Subject</FormLabel>
              <Input
                id="class-subject"
                name="subject"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Information Technology"
              />
              <FormErrorMessage>{fields.subject}</FormErrorMessage>
            </FormControl>

            <HStack spacing={4} align="flex-start">
              <FormControl isInvalid={Boolean(fields.level)}>
                <FormLabel htmlFor="class-level">Grade or level</FormLabel>
                <Input
                  id="class-level"
                  name="level"
                  value={level}
                  onChange={(e) => setLevel(e.target.value)}
                  placeholder="Form 4"
                />
                <FormErrorMessage>{fields.level}</FormErrorMessage>
              </FormControl>

              <FormControl isInvalid={Boolean(fields.academic_period)}>
                <FormLabel htmlFor="class-period">Academic period</FormLabel>
                <Input
                  id="class-period"
                  name="academic_period"
                  value={academicPeriod}
                  onChange={(e) => setAcademicPeriod(e.target.value)}
                  placeholder="2026 Term 1"
                />
                <FormErrorMessage>{fields.academic_period}</FormErrorMessage>
              </FormControl>
            </HStack>

            {isEditing && (
              <FormControl display="flex" alignItems="center">
                <Switch
                  id="class-active"
                  isChecked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                  colorScheme="cariteal"
                  mr={3}
                />
                <FormLabel htmlFor="class-active" mb={0}>
                  Class is active
                </FormLabel>
              </FormControl>
            )}

            <Text fontSize="sm" color="gray.600">
              ClassSortie stores the minimum information needed to run a formative check. You add
              students in the next step.
            </Text>

            <HStack>
              <Button type="submit" isLoading={isSaving} loadingText="Saving…">
                {isEditing ? 'Save changes' : 'Create class'}
              </Button>
              <Button variant="ghost" onClick={() => navigate('/app/classes')} type="button">
                Cancel
              </Button>
            </HStack>
          </VStack>
        </CardBody>
      </Card>
    </VStack>
  );
}
