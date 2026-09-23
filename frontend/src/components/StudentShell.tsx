import { Box, Container, Flex, Text, VStack } from '@chakra-ui/react';
import type { ReactNode } from 'react';
import { Brand } from './Brand';

/**
 * Layout for the public student pages.
 *
 * Designed for a phone at ~360px on a slow connection: single column, large
 * targets, no polling, and no data fetched that is not needed to answer.
 */
export function StudentShell({
  children,
  subtitle,
  googleAccountMode = false,
}: {
  children: ReactNode;
  subtitle?: string;
  /** When true, footer explains school Google sign-in instead of anonymous join. */
  googleAccountMode?: boolean;
}) {
  return (
    <Flex direction="column" minH="100vh" bg="sand.100">
      <Box as="header" bg="ocean.800" color="white" py={3}>
        <Container maxW="30rem" px={4}>
          <Brand variant="light" />
          {subtitle && (
            <Text fontSize="sm" color="sand.200" mt={1}>
              {subtitle}
            </Text>
          )}
        </Container>
      </Box>

      <Box as="main" id="main" flex="1" py={5}>
        <Container maxW="30rem" px={4}>
          <VStack align="stretch" spacing={4}>
            {children}
          </VStack>
        </Container>
      </Box>

      <Box as="footer" py={4}>
        <Container maxW="30rem" px={4}>
          <Text fontSize="xs" color="gray.600">
            {googleAccountMode
              ? 'Sign in with your school Google account for this activity.'
              : 'Your answers go to your teacher for this activity only. No account needed.'}
          </Text>
        </Container>
      </Box>
    </Flex>
  );
}
