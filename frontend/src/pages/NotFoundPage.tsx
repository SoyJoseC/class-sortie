import { Button, Center, Heading, Text, VStack } from '@chakra-ui/react';
import { Link } from 'react-router-dom';
import { Brand } from '@/components/Brand';

export function NotFoundPage() {
  return (
    <Center minH="100vh" bg="sand.100" px={4}>
      <VStack spacing={5} textAlign="center" maxW="md">
        <Brand size="lg" showTagline />
        <Heading size="lg" color="ocean.800">
          Page not found
        </Heading>
        <Text color="gray.700">
          If you are a student trying to join an activity, enter the code your teacher showed
          you.
        </Text>
        <VStack spacing={2}>
          <Button as={Link} to="/join" variant="accent">
            Join with a code
          </Button>
          <Button as={Link} to="/app" variant="ghost">
            Teacher dashboard
          </Button>
        </VStack>
      </VStack>
    </Center>
  );
}
