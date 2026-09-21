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
import { Link } from 'react-router-dom';
import { useActivitiesQuery } from '@/api/caricueApi';
import { errorMessage } from '@/api/baseQuery';
import { EmptyState, ErrorState, LoadingState } from '@/components/StateViews';
import { formatDateTime } from '@/utils/insightFormat';

export function ActivityListPage() {
  const { data, isLoading, isError, error, refetch } = useActivitiesQuery();

  if (isLoading) return <LoadingState label="Loading activities…" />;
  if (isError || !data) {
    return <ErrorState message={errorMessage(error)} onRetry={() => void refetch()} />;
  }

  return (
    <VStack spacing={5} align="stretch">
      <Flex justify="space-between" align="center" wrap="wrap" gap={3}>
        <Box>
          <Heading size="lg">Activities</Heading>
          <Text color="gray.600">
            Short formative checks. Launch one to collect responses from a class.
          </Text>
        </Box>
        <Button as={Link} to="/app/activities/new" variant="accent">
          Create an activity
        </Button>
      </Flex>

      {data.results.length === 0 ? (
        <EmptyState
          title="No activities yet"
          description="An activity is one to five questions you can launch in a couple of minutes. Students join with a code — no accounts needed."
          action={
            <Button as={Link} to="/app/activities/new" variant="accent">
              Create an activity
            </Button>
          }
        />
      ) : (
        <Card borderWidth="1px" borderColor="sand.200">
          <CardBody overflowX="auto">
            <Table size="sm">
              <Thead>
                <Tr>
                  <Th>Title</Th>
                  <Th>Class</Th>
                  <Th>Topic</Th>
                  <Th isNumeric>Questions</Th>
                  <Th>Status</Th>
                  <Th>Created</Th>
                  <Th />
                </Tr>
              </Thead>
              <Tbody>
                {data.results.map((activity) => (
                  <Tr key={activity.id}>
                    <Td fontWeight="600">{activity.title}</Td>
                    <Td>{activity.classroom_name}</Td>
                    <Td maxW="20rem">
                      <Text noOfLines={1} color="gray.600">
                        {activity.topic || '—'}
                      </Text>
                    </Td>
                    <Td isNumeric>{activity.question_count}</Td>
                    <Td>
                      <Badge
                        colorScheme={activity.status === 'published' ? 'cariteal' : 'gray'}
                        variant="subtle"
                      >
                        {activity.status}
                      </Badge>
                    </Td>
                    <Td whiteSpace="nowrap">{formatDateTime(activity.created_at)}</Td>
                    <Td>
                      <HStack spacing={1}>
                        <Button
                          as={Link}
                          to={`/app/activities/${activity.id}`}
                          size="xs"
                          variant="ghost"
                        >
                          Edit
                        </Button>
                      </HStack>
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </CardBody>
        </Card>
      )}
    </VStack>
  );
}
