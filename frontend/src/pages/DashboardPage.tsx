import {
  Badge,
  Box,
  Button,
  Card,
  CardBody,
  CardHeader,
  Divider,
  Flex,
  Heading,
  HStack,
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
import { Link, useNavigate } from 'react-router-dom';
import { useCreateFollowUpActivityMutation, useOverviewQuery } from '@/api/caricueApi';
import { errorMessage } from '@/api/baseQuery';
import { EmptyState, ErrorState, LoadingState } from '@/components/StateViews';
import { StatTile } from '@/components/StatTile';
import {
  formatCompletion,
  formatDateTime,
  formatPercent,
  formatSessionCode,
} from '@/utils/insightFormat';

export function DashboardPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const [createFollowUp, followUpState] = useCreateFollowUpActivityMutation();
  const { data, isLoading, isError, error, refetch } = useOverviewQuery(undefined, {
    refetchOnMountOrArgChange: true,
  });

  if (isLoading) return <LoadingState label="Loading your dashboard…" />;
  if (isError || !data) {
    return <ErrorState message={errorMessage(error)} onRetry={() => void refetch()} />;
  }

  const {
    counts,
    classrooms,
    recent_activities,
    open_sessions,
    recent_results,
    pending_followups,
  } = data;

  async function handleCreateFollowUp(sessionId: number) {
    try {
      const result = await createFollowUp({ sessionId, include_confidence: true }).unwrap();
      navigate(`/app/activities/${result.activity_id}`);
    } catch (err) {
      toast({ title: errorMessage(err), status: 'error' });
    }
  }

  return (
    <VStack spacing={6} align="stretch">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap={3}>
        <Box>
          <Heading size="lg">Welcome back, {data.teacher.full_name.split(' ')[0]}</Heading>
          <Text color="gray.600">
            Check what students understand, then decide what to teach next.
          </Text>
        </Box>
        <HStack>
          <Button as={Link} to="/app/classes/new" variant="outline">
            Create a class
          </Button>
          <Button as={Link} to="/app/activities/new" variant="accent">
            Create an activity
          </Button>
        </HStack>
      </Flex>

      <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
        <StatTile label="Classes" value={String(counts.classrooms)} accent="ocean" />
        <StatTile label="Students" value={String(counts.students)} accent="cariteal" />
        <StatTile label="Activities" value={String(counts.activities)} accent="ocean" />
        <StatTile
          label="Open sessions"
          value={String(counts.open_sessions)}
          accent={counts.open_sessions > 0 ? 'coral' : 'gray'}
        />
      </SimpleGrid>

      {open_sessions.length > 0 && (
        <Card borderWidth="1px" borderColor="coral.200" bg="coral.50">
          <CardHeader pb={2}>
            <Heading size="sm">Sessions open right now</Heading>
          </CardHeader>
          <CardBody pt={0}>
            <Stack spacing={3} divider={<Divider borderColor="coral.200" />}>
              {open_sessions.map((session) => (
                <Flex
                  key={session.id}
                  justify="space-between"
                  align="center"
                  wrap="wrap"
                  gap={2}
                >
                  <Box>
                    <Text fontWeight="700" color="ocean.800">
                      {session.activity_title}
                    </Text>
                    <Text fontSize="sm" color="gray.700">
                      {session.classroom_name} · code{' '}
                      <Box as="span" fontFamily="mono" fontWeight="700">
                        {formatSessionCode(session.code)}
                      </Box>{' '}
                      · {session.submitted_count} submitted
                    </Text>
                  </Box>
                  <HStack>
                    <Button
                      as={Link}
                      to={`/app/sessions/${session.id}/launch`}
                      size="sm"
                      variant="outline"
                    >
                      Show code
                    </Button>
                    <Button
                      as={Link}
                      to={`/app/sessions/${session.id}`}
                      size="sm"
                      variant="accent"
                    >
                      Live results
                    </Button>
                  </HStack>
                </Flex>
              ))}
            </Stack>
          </CardBody>
        </Card>
      )}

      {(pending_followups?.length ?? 0) > 0 && (
        <Card borderWidth="1px" borderColor="ocean.200" bg="ocean.50">
          <CardHeader pb={2}>
            <Heading size="sm">Follow up on these</Heading>
            <Text fontSize="sm" color="gray.600">
              You changed your plan after these checks but have not run a follow-up on the same
              topic yet.
            </Text>
          </CardHeader>
          <CardBody pt={0}>
            <Stack spacing={3} divider={<Divider borderColor="ocean.200" />}>
              {pending_followups.map((item) => (
                <Flex key={item.last_session_id} justify="space-between" wrap="wrap" gap={2}>
                  <Box>
                    <Text fontWeight="700" color="ocean.800">
                      {item.classroom_name} · {item.topic}
                    </Text>
                    <Text fontSize="sm" color="gray.700">
                      Session {item.last_session_code} · closed {item.days_since} day
                      {item.days_since === 1 ? '' : 's'} ago
                    </Text>
                    {item.primary_gap && (
                      <Text fontSize="sm" color="gray.600" fontStyle="italic">
                        &ldquo;{item.primary_gap}&rdquo;
                      </Text>
                    )}
                    {item.top_misconception_title && (
                      <Text fontSize="xs" color="gray.600" mt={1}>
                        Top misconception: {item.top_misconception_title}
                      </Text>
                    )}
                  </Box>
                  <HStack>
                    <Button
                      as={Link}
                      to={`/app/sessions/${item.last_session_id}/reflection`}
                      size="sm"
                      variant="outline"
                    >
                      View results
                    </Button>
                    <Button
                      size="sm"
                      variant="accent"
                      onClick={() => void handleCreateFollowUp(item.last_session_id)}
                      isLoading={followUpState.isLoading}
                    >
                      Create follow-up
                    </Button>
                  </HStack>
                </Flex>
              ))}
            </Stack>
          </CardBody>
        </Card>
      )}

      <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
        <Card borderWidth="1px" borderColor="sand.200">
          <CardHeader pb={2}>
            <Flex justify="space-between" align="center">
              <Heading size="sm">Your classes</Heading>
              <Button as={Link} to="/app/classes" size="xs" variant="ghost">
                View all
              </Button>
            </Flex>
          </CardHeader>
          <CardBody pt={0}>
            {classrooms.length === 0 ? (
              <EmptyState
                title="No classes yet"
                description="Create a class, then add students by hand or import a CSV roster."
                action={
                  <Button as={Link} to="/app/classes/new" size="sm" variant="accent">
                    Create a class
                  </Button>
                }
              />
            ) : (
              <Stack spacing={2} divider={<Divider />}>
                {classrooms.slice(0, 5).map((classroom) => (
                  <Flex key={classroom.id} justify="space-between" align="center" gap={2}>
                    <Box>
                      <Text fontWeight="600" color="ocean.800">
                        {classroom.name}
                      </Text>
                      <Text fontSize="sm" color="gray.600">
                        {classroom.subject || 'No subject'} · {classroom.roster_size} students ·{' '}
                        {classroom.activity_count} activities
                      </Text>
                    </Box>
                    <Button
                      as={Link}
                      to={`/app/classes/${classroom.id}`}
                      size="sm"
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
            <Flex justify="space-between" align="center">
              <Heading size="sm">Recently created activities</Heading>
              <Button as={Link} to="/app/activities" size="xs" variant="ghost">
                View all
              </Button>
            </Flex>
          </CardHeader>
          <CardBody pt={0}>
            {recent_activities.length === 0 ? (
              <EmptyState
                title="No activities yet"
                description="An activity is one to five quick questions you can launch in a couple of minutes."
                action={
                  <Button as={Link} to="/app/activities/new" size="sm" variant="accent">
                    Create an activity
                  </Button>
                }
              />
            ) : (
              <Stack spacing={2} divider={<Divider />}>
                {recent_activities.map((activity) => (
                  <Flex key={activity.id} justify="space-between" align="center" gap={2}>
                    <Box>
                      <HStack spacing={2}>
                        <Text fontWeight="600" color="ocean.800">
                          {activity.title}
                        </Text>
                        <Badge
                          colorScheme={activity.status === 'published' ? 'cariteal' : 'gray'}
                          variant="subtle"
                        >
                          {activity.status}
                        </Badge>
                      </HStack>
                      <Text fontSize="sm" color="gray.600">
                        {activity.classroom_name} · {activity.question_count} questions
                      </Text>
                    </Box>
                    <Button
                      as={Link}
                      to={`/app/activities/${activity.id}`}
                      size="sm"
                      variant="ghost"
                    >
                      Edit
                    </Button>
                  </Flex>
                ))}
              </Stack>
            )}
          </CardBody>
        </Card>
      </SimpleGrid>

      <Card borderWidth="1px" borderColor="sand.200">
        <CardHeader pb={2}>
          <Heading size="sm">Recent formative results</Heading>
          <Text fontSize="sm" color="gray.600">
            All figures below are calculated from student responses.
          </Text>
        </CardHeader>
        <CardBody pt={0} overflowX="auto">
          {recent_results.length === 0 ? (
            <EmptyState
              title="No sessions run yet"
              description="Launch an activity to collect responses. Results and suggestions appear here afterwards."
            />
          ) : (
            <Table size="sm" variant="simple">
              <Thead>
                <Tr>
                  <Th>Activity</Th>
                  <Th>Class</Th>
                  <Th>Started</Th>
                  <Th isNumeric>Submitted</Th>
                  <Th isNumeric>Correct</Th>
                  <Th isNumeric>Needs attention</Th>
                  <Th>Reflection</Th>
                  <Th />
                </Tr>
              </Thead>
              <Tbody>
                {recent_results.map((result) => (
                  <Tr key={result.session.id}>
                    <Td fontWeight="600">{result.session.activity_title}</Td>
                    <Td>{result.session.classroom_name}</Td>
                    <Td whiteSpace="nowrap">{formatDateTime(result.session.started_at)}</Td>
                    <Td isNumeric>
                      {formatCompletion({
                        submitted_count: result.submitted_count,
                        roster_size: result.session.roster_size,
                      })}
                    </Td>
                    <Td isNumeric>{formatPercent(result.overall_correctness_percentage)}</Td>
                    <Td isNumeric>{result.needs_attention_count}</Td>
                    <Td>
                      {result.session.has_reflection ? (
                        <Badge colorScheme="cariteal" variant="subtle">
                          Recorded
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
                        to={`/app/sessions/${result.session.id}`}
                        size="xs"
                        variant="ghost"
                      >
                        Open
                      </Button>
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          )}
        </CardBody>
      </Card>
    </VStack>
  );
}
