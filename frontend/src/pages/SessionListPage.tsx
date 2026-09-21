import { useState } from 'react';
import {
  Badge,
  Box,
  Button,
  ButtonGroup,
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
import { useSessionsQuery } from '@/api/caricueApi';
import { errorMessage } from '@/api/baseQuery';
import { EmptyState, ErrorState, LoadingState } from '@/components/StateViews';
import { formatDateTime, formatSessionCode } from '@/utils/insightFormat';

type Filter = 'all' | 'open' | 'closed';

export function SessionListPage() {
  const [filter, setFilter] = useState<Filter>('all');
  const { data, isLoading, isError, error, refetch } = useSessionsQuery(
    filter === 'all' ? undefined : { status: filter }
  );

  return (
    <VStack spacing={5} align="stretch">
      <Flex justify="space-between" align="center" wrap="wrap" gap={3}>
        <Box>
          <Heading size="lg">Sessions</Heading>
          <Text color="gray.600">
            Every time you launch an activity, the responses land in a session.
          </Text>
        </Box>
        <ButtonGroup size="sm" isAttached variant="outline">
          {(['all', 'open', 'closed'] as Filter[]).map((value) => (
            <Button
              key={value}
              onClick={() => setFilter(value)}
              bg={filter === value ? 'ocean.50' : undefined}
              fontWeight={filter === value ? 700 : 400}
              aria-pressed={filter === value}
            >
              {value === 'all' ? 'All' : value}
            </Button>
          ))}
        </ButtonGroup>
      </Flex>

      {isLoading && <LoadingState label="Loading sessions…" />}
      {isError && <ErrorState message={errorMessage(error)} onRetry={() => void refetch()} />}

      {data && data.results.length === 0 && (
        <EmptyState
          title="No sessions to show"
          description="Launch an activity to start collecting responses. You will get a short code and a QR code to project."
          action={
            <Button as={Link} to="/app/activities" variant="accent">
              Go to activities
            </Button>
          }
        />
      )}

      {data && data.results.length > 0 && (
        <Card borderWidth="1px" borderColor="sand.200">
          <CardBody overflowX="auto">
            <Table size="sm">
              <Thead>
                <Tr>
                  <Th>Activity</Th>
                  <Th>Class</Th>
                  <Th>Code</Th>
                  <Th>Status</Th>
                  <Th isNumeric>Submitted</Th>
                  <Th>Started</Th>
                  <Th>Next step</Th>
                  <Th />
                </Tr>
              </Thead>
              <Tbody>
                {data.results.map((session) => (
                  <Tr key={session.id}>
                    <Td fontWeight="600">{session.activity_title}</Td>
                    <Td>{session.classroom_name}</Td>
                    <Td fontFamily="mono">{formatSessionCode(session.code)}</Td>
                    <Td>
                      <Badge
                        colorScheme={session.status === 'open' ? 'cariteal' : 'gray'}
                        variant="subtle"
                      >
                        {session.status}
                      </Badge>
                    </Td>
                    <Td isNumeric>
                      {session.submitted_count}
                      {session.roster_size > 0 ? ` / ${session.roster_size}` : ''}
                    </Td>
                    <Td whiteSpace="nowrap">{formatDateTime(session.started_at)}</Td>
                    <Td>
                      {session.status === 'open' ? (
                        <Text fontSize="sm" color="cariteal.700">
                          Collecting
                        </Text>
                      ) : session.has_reflection ? (
                        <Text fontSize="sm" color="gray.600">
                          Recorded
                        </Text>
                      ) : (
                        <Text fontSize="sm" color="coral.700" fontWeight="600">
                          Not recorded
                        </Text>
                      )}
                    </Td>
                    <Td>
                      <HStack spacing={1}>
                        <Button
                          as={Link}
                          to={`/app/sessions/${session.id}`}
                          size="xs"
                          variant="ghost"
                        >
                          Results
                        </Button>
                        {session.status === 'open' && (
                          <Button
                            as={Link}
                            to={`/app/sessions/${session.id}/launch`}
                            size="xs"
                            variant="ghost"
                          >
                            Code
                          </Button>
                        )}
                        {session.status === 'closed' && (
                          <Button
                            as={Link}
                            to={`/app/sessions/${session.id}/reflection`}
                            size="xs"
                            variant="ghost"
                          >
                            Reflect
                          </Button>
                        )}
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
