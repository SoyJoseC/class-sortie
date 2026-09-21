import {
  Badge,
  Box,
  Button,
  Card,
  CardBody,
  Flex,
  Heading,
  HStack,
  SimpleGrid,
  Text,
  VStack,
} from '@chakra-ui/react';
import { Link } from 'react-router-dom';
import { useClassroomsQuery } from '@/api/caricueApi';
import { errorMessage } from '@/api/baseQuery';
import { EmptyState, ErrorState, LoadingState } from '@/components/StateViews';

export function ClassListPage() {
  const { data, isLoading, isError, error, refetch } = useClassroomsQuery();

  if (isLoading) return <LoadingState label="Loading your classes…" />;
  if (isError || !data) {
    return <ErrorState message={errorMessage(error)} onRetry={() => void refetch()} />;
  }

  return (
    <VStack spacing={5} align="stretch">
      <Flex justify="space-between" align="center" wrap="wrap" gap={3}>
        <Box>
          <Heading size="lg">Classes</Heading>
          <Text color="gray.600">
            A class holds a roster and the activities you run with that group.
          </Text>
        </Box>
        <Button as={Link} to="/app/classes/new" variant="accent">
          Create a class
        </Button>
      </Flex>

      {data.results.length === 0 ? (
        <EmptyState
          title="No classes yet"
          description="Create your first class, then add students manually or import a CSV roster exported from your school system."
          action={
            <Button as={Link} to="/app/classes/new" variant="accent">
              Create a class
            </Button>
          }
        />
      ) : (
        <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
          {data.results.map((classroom) => (
            <Card key={classroom.id} borderWidth="1px" borderColor="sand.200">
              <CardBody>
                <VStack align="stretch" spacing={3}>
                  <HStack justify="space-between" align="flex-start">
                    <Heading size="sm" color="ocean.800">
                      {classroom.name}
                    </Heading>
                    {!classroom.is_active && (
                      <Badge colorScheme="gray" variant="subtle">
                        Inactive
                      </Badge>
                    )}
                  </HStack>
                  <Text fontSize="sm" color="gray.600">
                    {[classroom.subject, classroom.level, classroom.academic_period]
                      .filter(Boolean)
                      .join(' · ') || 'No subject set'}
                  </Text>
                  <HStack spacing={4} fontSize="sm" color="ocean.700" fontWeight="600">
                    <Text>{classroom.roster_size} students</Text>
                    <Text>{classroom.activity_count} activities</Text>
                  </HStack>
                  <Button
                    as={Link}
                    to={`/app/classes/${classroom.id}`}
                    size="sm"
                    variant="outline"
                  >
                    Manage class
                  </Button>
                </VStack>
              </CardBody>
            </Card>
          ))}
        </SimpleGrid>
      )}
    </VStack>
  );
}
