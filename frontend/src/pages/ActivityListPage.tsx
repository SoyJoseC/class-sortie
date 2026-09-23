import { useRef, useState } from 'react';
import {
  Alert,
  AlertIcon,
  Badge,
  Box,
  Button,
  Card,
  CardBody,
  Flex,
  FormControl,
  FormLabel,
  Heading,
  HStack,
  List,
  ListItem,
  Select,
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
import {
  useActivitiesQuery,
  useClassroomsQuery,
  useImportActivityMutation,
} from '@/api/caricueApi';
import { errorMessage } from '@/api/baseQuery';
import { EmptyState, ErrorState, LoadingState } from '@/components/StateViews';
import { formatDateTime } from '@/utils/insightFormat';

export function ActivityListPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const fileInput = useRef<HTMLInputElement>(null);

  const { data, isLoading, isError, error, refetch } = useActivitiesQuery();
  const classrooms = useClassroomsQuery();
  const [importActivity, importState] = useImportActivityMutation();

  const [importClassroom, setImportClassroom] = useState<number | ''>('');

  if (isLoading || classrooms.isLoading) return <LoadingState label="Loading activities…" />;
  if (isError || !data) {
    return <ErrorState message={errorMessage(error)} onRetry={() => void refetch()} />;
  }

  const classOptions = classrooms.data?.results ?? [];

  async function handleImport(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file || importClassroom === '') return;
    try {
      const result = await importActivity({ classroom: importClassroom, file }).unwrap();
      if (result.row_errors.length > 0) {
        toast({
          title: 'Import had row errors',
          description: `${result.row_errors.length} row(s) need fixing.`,
          status: 'warning',
          duration: 5000,
        });
        return;
      }
      if (result.activity_id) {
        toast({ title: 'Activity imported', status: 'success', duration: 2500 });
        navigate(`/app/activities/${result.activity_id}`);
      }
    } catch {
      // Error banner below.
    } finally {
      if (fileInput.current) fileInput.current.value = '';
    }
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
        <HStack flexWrap="wrap">
          <Button as="a" href="/api/activities/template.csv" download variant="outline">
            Download CSV template
          </Button>
          <Button as={Link} to="/app/activities/new" variant="accent">
            Create an activity
          </Button>
        </HStack>
      </Flex>

      <Card borderWidth="1px" borderColor="sand.200">
        <CardBody>
          <Heading size="sm" mb={3}>
            Import from file
          </Heading>
          <Flex gap={4} direction={{ base: 'column', md: 'row' }} align={{ md: 'flex-end' }}>
            <FormControl maxW="20rem" isRequired>
              <FormLabel htmlFor="import-class">Class for new draft</FormLabel>
              <Select
                id="import-class"
                placeholder="Select a class"
                value={importClassroom}
                onChange={(e) =>
                  setImportClassroom(e.target.value ? Number(e.target.value) : '')
                }
              >
                {classOptions.map((room) => (
                  <option key={room.id} value={room.id}>
                    {room.name}
                  </option>
                ))}
              </Select>
            </FormControl>
            <Button
              variant="outline"
              isDisabled={importClassroom === ''}
              isLoading={importState.isLoading}
              onClick={() => fileInput.current?.click()}
            >
              Import CSV or JSON
            </Button>
            <input
              ref={fileInput}
              type="file"
              accept=".csv,.json,text/csv,application/json"
              hidden
              onChange={handleImport}
            />
          </Flex>
          {importState.error && (
            <Alert status="error" mt={4} borderRadius="md">
              <AlertIcon />
              <Text fontSize="sm">{errorMessage(importState.error)}</Text>
            </Alert>
          )}
          {importState.data?.row_errors.length ? (
            <Box mt={4}>
              <Text fontSize="sm" fontWeight="600" mb={2}>
                Row errors
              </Text>
              <List spacing={1} fontSize="sm" color="gray.700">
                {importState.data.row_errors.map((row) => (
                  <ListItem key={`${row.line}-${row.message}`}>
                    Line {row.line}: {row.message}
                  </ListItem>
                ))}
              </List>
            </Box>
          ) : null}
        </CardBody>
      </Card>

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
                      <Button as={Link} to={`/app/activities/${activity.id}`} size="sm">
                        Open
                      </Button>
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
