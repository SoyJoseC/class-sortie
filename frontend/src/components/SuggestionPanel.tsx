import {
  Alert,
  AlertIcon,
  Box,
  Card,
  CardBody,
  Heading,
  HStack,
  Text,
  VStack,
} from '@chakra-ui/react';
import type { Suggestion } from '@/api/types';
import { SuggestionBadge } from './FactBadge';

const CATEGORY_LABELS: Record<Suggestion['category'], string> = {
  misconception: 'Possible misconception',
  follow_up: 'Follow-up idea',
  next_question: 'Question for next lesson',
  summary: 'Summary of open responses',
};

/**
 * Advisory output from the configured insight provider.
 *
 * Kept in its own visually distinct column so a teacher never mistakes it for
 * measured data. Nothing here writes to student records.
 */
export function SuggestionPanel({ suggestions }: { suggestions: Suggestion[] }) {
  return (
    <Card borderWidth="1px" borderColor="coral.200" bg="coral.50">
      <CardBody>
        <VStack align="stretch" spacing={3}>
          <HStack justify="space-between">
            <Heading size="sm" color="ocean.800">
              Suggestions
            </Heading>
            <SuggestionBadge source={suggestions[0]?.source} />
          </HStack>

          <Text fontSize="sm" color="gray.700">
            Generated from the response patterns above. Nothing is graded or recorded from this
            panel — you decide what to act on.
          </Text>

          {suggestions.length === 0 ? (
            <Alert status="info" borderRadius="md" fontSize="sm">
              <AlertIcon />
              Not enough responses yet to suggest anything useful.
            </Alert>
          ) : (
            <VStack align="stretch" spacing={3}>
              {suggestions.map((suggestion, index) => (
                <Box
                  key={`${suggestion.category}-${index}`}
                  bg="white"
                  borderWidth="1px"
                  borderColor="coral.200"
                  borderRadius="md"
                  p={3}
                >
                  <Text
                    fontSize="xs"
                    fontWeight="700"
                    textTransform="uppercase"
                    color="coral.700"
                    mb={1}
                  >
                    {CATEGORY_LABELS[suggestion.category] ?? suggestion.category}
                  </Text>
                  <Text fontWeight="700" color="ocean.800">
                    {suggestion.title}
                  </Text>
                  <Text fontSize="sm" color="gray.700" whiteSpace="pre-wrap">
                    {suggestion.body}
                  </Text>
                </Box>
              ))}
            </VStack>
          )}
        </VStack>
      </CardBody>
    </Card>
  );
}
