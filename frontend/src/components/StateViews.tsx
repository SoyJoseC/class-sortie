import {
  Alert,
  AlertDescription,
  AlertIcon,
  AlertTitle,
  Box,
  Button,
  Center,
  Spinner,
  Text,
  VStack,
} from '@chakra-ui/react';
import type { ReactNode } from 'react';

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <Center py={12} role="status" aria-live="polite">
      <VStack spacing={3}>
        <Spinner size="lg" color="ocean.600" thickness="3px" speed="0.7s" />
        <Text color="ocean.700">{label}</Text>
      </VStack>
    </Center>
  );
}

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export function ErrorState({
  title = 'Something went wrong',
  message,
  onRetry,
}: ErrorStateProps) {
  return (
    <Alert
      status="error"
      variant="subtle"
      flexDirection="column"
      alignItems="flex-start"
      borderRadius="md"
      py={4}
    >
      <Box display="flex" alignItems="center">
        <AlertIcon />
        <AlertTitle>{title}</AlertTitle>
      </Box>
      <AlertDescription mt={2}>{message}</AlertDescription>
      {onRetry && (
        <Button mt={3} size="sm" variant="outline" onClick={onRetry}>
          Try again
        </Button>
      )}
    </Alert>
  );
}

interface EmptyStateProps {
  title: string;
  description: string;
  action?: ReactNode;
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <VStack
      spacing={3}
      py={10}
      px={6}
      bg="white"
      borderWidth="1px"
      borderStyle="dashed"
      borderColor="sand.300"
      borderRadius="lg"
      textAlign="center"
    >
      <Text fontWeight="700" color="ocean.800" fontSize="lg">
        {title}
      </Text>
      <Text color="gray.600" maxW="lg">
        {description}
      </Text>
      {action}
    </VStack>
  );
}
