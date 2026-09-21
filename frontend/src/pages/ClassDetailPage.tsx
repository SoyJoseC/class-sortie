import { useRef, useState } from 'react';
import {
  Alert,
  AlertIcon,
  Badge,
  Box,
  Button,
  Card,
  CardBody,
  CardHeader,
  Flex,
  FormControl,
  FormErrorMessage,
  FormHelperText,
  FormLabel,
  Heading,
  HStack,
  IconButton,
  Input,
  List,
  ListItem,
  SimpleGrid,
  Stack,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
  useToast,
  VStack,
} from '@chakra-ui/react';
import { Link, useParams } from 'react-router-dom';
import {
  useActivitiesQuery,
  useAddStudentToClassMutation,
  useClassroomQuery,
  useImportRosterMutation,
  useRemoveEnrollmentMutation,
  useRosterQuery,
  useSessionsQuery,
  useTopicTimelineQuery,
} from '@/api/caricueApi';
import { errorMessage, fieldErrors } from '@/api/baseQuery';
import { EmptyState, ErrorState, LoadingState } from '@/components/StateViews';
import { StatTile } from '@/components/StatTile';
import { formatDateTime, formatPercent, formatSessionCode } from '@/utils/insightFormat';

export function ClassDetailPage() {
  const { id } = useParams<{ id: string }>();
  const classroomId = Number(id);
  const toast = useToast();

  const classroom = useClassroomQuery(classroomId);
  const roster = useRosterQuery(classroomId);
  const activities = useActivitiesQuery({ classroom: classroomId });
  const sessions = useSessionsQuery({ classroom: classroomId });
  const topicTimeline = useTopicTimelineQuery(classroomId);

  const [addStudent, addState] = useAddStudentToClassMutation();
  const [importRoster, importState] = useImportRosterMutation();
  const [removeEnrollment] = useRemoveEnrollmentMutation();

  const [displayName, setDisplayName] = useState('');
  const [identifier, setIdentifier] = useState('');
  const [touched, setTouched] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const addFields = fieldErrors(addState.error);
  const nameProblem =
    touched && !displayName.trim()
      ? 'Enter the student’s display name.'
      : addFields.display_name;

  if (classroom.isLoading) return <LoadingState label="Loading class…" />;
  if (classroom.isError || !classroom.data) {
    return <ErrorState message={errorMessage(classroom.error, 'Class not found.')} />;
  }

  async function handleAddStudent(event: React.FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (!displayName.trim()) return;
    try {
      await addStudent({
        classroomId,
        body: {
          display_name: displayName.trim(),
          school_identifier: identifier.trim(),
        },
      }).unwrap();
      setDisplayName('');
      setIdentifier('');
      setTouched(false);
      toast({ title: 'Student added', status: 'success', duration: 2500 });
    } catch {
      // Field errors render inline.
    }
  }

  async function handleImport(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const result = await importRoster({ classroomId, file }).unwrap();
      const summary = [
        `${result.created_students} new`,
        `${result.updated_students} updated`,
        `${result.created_enrollments} enrolled`,
      ].join(', ');
      toast({
        title: 'Roster imported',
        description: summary,
        status: result.row_errors.length > 0 ? 'warning' : 'success',
        duration: 5000,
      });
    } catch {
      // Error banner renders below.
    } finally {
      // Allow re-selecting the same file after a fix.
      if (fileInput.current) fileInput.current.value = '';
    }
  }

  const data = classroom.data;
  const enrollments = roster.data ?? [];

  return (
    <VStack spacing={6} align="stretch">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap={3}>
        <Box>
          <Heading size="lg">{data.name}</Heading>
          <Text color="gray.600">
            {[data.subject, data.level, data.academic_period].filter(Boolean).join(' · ') ||
              'No subject set'}
          </Text>
        </Box>
        <HStack>
          <Button as={Link} to={`/app/classes/${classroomId}/edit`} variant="outline">
            Edit class
          </Button>
          <Button
            as={Link}
            to={`/app/activities/new?classroom=${classroomId}`}
            variant="accent"
          >
            Create an activity
          </Button>
        </HStack>
      </Flex>

      <SimpleGrid columns={{ base: 2, md: 3 }} spacing={4}>
        <StatTile label="Students" value={String(data.roster_size)} accent="cariteal" />
        <StatTile label="Activities" value={String(data.activity_count)} accent="ocean" />
        <StatTile
          label="Sessions run"
          value={String(sessions.data?.count ?? 0)}
          accent="ocean"
        />
      </SimpleGrid>

      <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
        <Card borderWidth="1px" borderColor="sand.200">
          <CardHeader pb={2}>
            <Heading size="sm">Add a student</Heading>
            <Text fontSize="sm" color="gray.600">
              Only a display name is required. Add a roster identifier if you want students to
              identify themselves with it when joining.
            </Text>
          </CardHeader>
          <CardBody pt={0}>
            <VStack
              as="form"
              spacing={3}
              align="stretch"
              onSubmit={handleAddStudent}
              noValidate
            >
              {addState.error && !Object.keys(addFields).length && (
                <ErrorState message={errorMessage(addState.error)} />
              )}

              <FormControl isInvalid={Boolean(nameProblem)} isRequired>
                <FormLabel htmlFor="student-name">Display name</FormLabel>
                <Input
                  id="student-name"
                  name="display_name"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="Amara Joseph"
                />
                <FormErrorMessage>{nameProblem}</FormErrorMessage>
              </FormControl>

              <FormControl isInvalid={Boolean(addFields.school_identifier)}>
                <FormLabel htmlFor="student-identifier">School identifier (optional)</FormLabel>
                <Input
                  id="student-identifier"
                  name="school_identifier"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="STU-001"
                />
                <FormErrorMessage>{addFields.school_identifier}</FormErrorMessage>
              </FormControl>

              <Button
                type="submit"
                isLoading={addState.isLoading}
                loadingText="Adding…"
                alignSelf="flex-start"
              >
                Add student
              </Button>
            </VStack>
          </CardBody>
        </Card>

        <Card borderWidth="1px" borderColor="sand.200">
          <CardHeader pb={2}>
            <Heading size="sm">Import a CSV roster</Heading>
            <Text fontSize="sm" color="gray.600">
              Export a participant list from your school system, trim it to these columns, and
              upload it. Re-importing the same file updates students instead of duplicating
              them.
            </Text>
          </CardHeader>
          <CardBody pt={0}>
            <VStack spacing={3} align="stretch">
              <Box bg="sand.100" p={3} borderRadius="md" fontFamily="mono" fontSize="sm">
                display_name,school_identifier,email
              </Box>

              <FormControl>
                <FormLabel htmlFor="roster-file">CSV file</FormLabel>
                <Input
                  id="roster-file"
                  ref={fileInput}
                  type="file"
                  accept=".csv,text/csv"
                  onChange={handleImport}
                  isDisabled={importState.isLoading}
                  py={1}
                />
                <FormHelperText>
                  Only <code>display_name</code> is required. Maximum 500 rows.
                </FormHelperText>
              </FormControl>

              <Button
                as="a"
                href="/api/roster-template.csv"
                download
                size="sm"
                variant="outline"
                alignSelf="flex-start"
              >
                Download CSV template
              </Button>

              {importState.isLoading && <Text fontSize="sm">Importing…</Text>}

              {importState.error && <ErrorState message={errorMessage(importState.error)} />}

              {importState.data && importState.data.row_errors.length > 0 && (
                <Alert status="warning" borderRadius="md" alignItems="flex-start">
                  <AlertIcon />
                  <Box>
                    <Text fontWeight="700">
                      {importState.data.row_errors.length} row(s) were skipped
                    </Text>
                    <List fontSize="sm" mt={1} spacing={1}>
                      {importState.data.row_errors.slice(0, 8).map((rowError) => (
                        <ListItem key={`${rowError.line}-${rowError.message}`}>
                          Line {rowError.line}: {rowError.message}
                        </ListItem>
                      ))}
                    </List>
                  </Box>
                </Alert>
              )}
            </VStack>
          </CardBody>
        </Card>
      </SimpleGrid>

      <Card borderWidth="1px" borderColor="sand.200">
        <CardHeader pb={2}>
          <Heading size="sm">Roster ({enrollments.length})</Heading>
        </CardHeader>
        <CardBody pt={0} overflowX="auto">
          {roster.isLoading ? (
            <LoadingState label="Loading roster…" />
          ) : enrollments.length === 0 ? (
            <EmptyState
              title="No students in this class"
              description="Add a student above or import a CSV roster to get started."
            />
          ) : (
            <Table size="sm">
              <Thead>
                <Tr>
                  <Th>Student</Th>
                  <Th>Identifier</Th>
                  <Th>Status</Th>
                  <Th />
                </Tr>
              </Thead>
              <Tbody>
                {enrollments.map((enrollment) => (
                  <Tr key={enrollment.id}>
                    <Td fontWeight="600">{enrollment.student_detail.display_name}</Td>
                    <Td fontFamily="mono" fontSize="sm">
                      {enrollment.student_detail.school_identifier || '—'}
                    </Td>
                    <Td>
                      <Badge
                        colorScheme={enrollment.is_active ? 'cariteal' : 'gray'}
                        variant="subtle"
                      >
                        {enrollment.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </Td>
                    <Td textAlign="right">
                      <IconButton
                        aria-label={`Remove ${enrollment.student_detail.display_name} from ${data.name}`}
                        size="xs"
                        variant="ghost"
                        colorScheme="coral"
                        icon={<Box aria-hidden="true">✕</Box>}
                        onClick={() =>
                          void removeEnrollment({ id: enrollment.id, classroomId })
                            .unwrap()
                            .catch(() =>
                              toast({
                                title: 'Could not remove that student',
                                status: 'error',
                              })
                            )
                        }
                      />
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          )}
        </CardBody>
      </Card>

      <Card borderWidth="1px" borderColor="sand.200">
        <CardHeader pb={2}>
          <Heading size="sm">Topic history</Heading>
          <Text fontSize="sm" color="gray.600">
            Closed sessions grouped by topic — track whether reteaching helped.
          </Text>
        </CardHeader>
        <CardBody pt={0} overflowX="auto">
          {topicTimeline.isLoading ? (
            <LoadingState label="Loading topic history…" />
          ) : (topicTimeline.data?.length ?? 0) === 0 ? (
            <Text fontSize="sm" color="gray.600">
              No closed sessions yet.
            </Text>
          ) : (
            <Stack spacing={4}>
              {topicTimeline.data?.map((group) => (
                <Box key={group.topic}>
                  <Text fontWeight="700" color="ocean.800" mb={2}>
                    {group.topic}
                  </Text>
                  <Table size="sm">
                    <Thead>
                      <Tr>
                        <Th>Code</Th>
                        <Th>Closed</Th>
                        <Th isNumeric>Correct</Th>
                        <Th>Reflection</Th>
                        <Th />
                      </Tr>
                    </Thead>
                    <Tbody>
                      {group.sessions.map((entry) => (
                        <Tr key={entry.id}>
                          <Td fontFamily="mono">{formatSessionCode(entry.code)}</Td>
                          <Td whiteSpace="nowrap">{formatDateTime(entry.closed_at)}</Td>
                          <Td isNumeric>{formatPercent(entry.correctness)}</Td>
                          <Td>
                            {entry.has_reflection ? (
                              <Badge colorScheme="cariteal" variant="subtle">
                                {entry.plan_impact ?? 'Recorded'}
                              </Badge>
                            ) : (
                              <Badge colorScheme="gray" variant="subtle">
                                Pending
                              </Badge>
                            )}
                          </Td>
                          <Td>
                            <Button
                              as={Link}
                              to={`/app/sessions/${entry.id}`}
                              size="xs"
                              variant="ghost"
                            >
                              Results
                            </Button>
                          </Td>
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                </Box>
              ))}
            </Stack>
          )}
        </CardBody>
      </Card>

      <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
        <Card borderWidth="1px" borderColor="sand.200">
          <CardHeader pb={2}>
            <Heading size="sm">Activities for this class</Heading>
          </CardHeader>
          <CardBody pt={0}>
            {(activities.data?.results ?? []).length === 0 ? (
              <Text fontSize="sm" color="gray.600">
                No activities yet.
              </Text>
            ) : (
              <Stack spacing={2}>
                {activities.data?.results.map((activity) => (
                  <Flex key={activity.id} justify="space-between" align="center" gap={2}>
                    <Box>
                      <Text fontWeight="600">{activity.title}</Text>
                      <Text fontSize="sm" color="gray.600">
                        {activity.question_count} questions · {activity.status}
                      </Text>
                    </Box>
                    <Button
                      as={Link}
                      to={`/app/activities/${activity.id}`}
                      size="xs"
                      variant="ghost"
                    >
                      Open
                    </Button>
                  </Flex>
                ))}
              </Stack>
            )}
          </CardBody>
        </Card>

        <Card borderWidth="1px" borderColor="sand.200">
          <CardHeader pb={2}>
            <Heading size="sm">Previous sessions</Heading>
          </CardHeader>
          <CardBody pt={0}>
            {(sessions.data?.results ?? []).length === 0 ? (
              <Text fontSize="sm" color="gray.600">
                No sessions run with this class yet.
              </Text>
            ) : (
              <Stack spacing={2}>
                {sessions.data?.results.map((session) => (
                  <Flex key={session.id} justify="space-between" align="center" gap={2}>
                    <Box>
                      <Text fontWeight="600">{session.activity_title}</Text>
                      <Text fontSize="sm" color="gray.600">
                        {formatSessionCode(session.code)} · {formatDateTime(session.started_at)}{' '}
                        · {session.submitted_count} submitted
                      </Text>
                    </Box>
                    <HStack>
                      <Badge
                        colorScheme={session.status === 'open' ? 'coral' : 'gray'}
                        variant="subtle"
                      >
                        {session.status}
                      </Badge>
                      <Button
                        as={Link}
                        to={`/app/sessions/${session.id}`}
                        size="xs"
                        variant="ghost"
                      >
                        Results
                      </Button>
                    </HStack>
                  </Flex>
                ))}
              </Stack>
            )}
          </CardBody>
        </Card>
      </SimpleGrid>
    </VStack>
  );
}
