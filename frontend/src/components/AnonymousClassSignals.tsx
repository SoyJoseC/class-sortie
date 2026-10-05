import { Box, Card, CardBody, Heading, HStack, Text, VStack } from '@chakra-ui/react';
import type { SessionFacts } from '@/api/types';
import { FactBadge } from './FactBadge';
import { hasPerformanceConfidenceSignal } from '@/utils/insightFormat';

/** Count-only view of confidence-vs-performance signals (no student names). */
export function AnonymousClassSignals({ facts }: { facts: SessionFacts }) {
  if (!hasPerformanceConfidenceSignal(facts)) {
    return null;
  }

  const confidentWrongByQuestion = groupByQuestion(facts.high_confidence_incorrect);
  const unsureCorrectByQuestion = groupByQuestion(facts.low_confidence_correct);

  return (
    <Card borderWidth="1px" borderColor="sand.200">
      <CardBody>
        <HStack justify="space-between" mb={3}>
          <Heading size="sm" color="ocean.800">
            Confidence versus performance
          </Heading>
          <FactBadge />
        </HStack>
        <Text fontSize="sm" color="gray.600" mb={4}>
          Counts only — use this to prompt class discussion without naming individuals.
        </Text>
        <VStack align="stretch" spacing={4}>
          {facts.high_confidence_incorrect.length > 0 && (
            <Box>
              <Text fontSize="sm" fontWeight="700" color="coral.700" mb={2}>
                Confident but wrong ({facts.high_confidence_incorrect.length})
              </Text>
              <VStack align="stretch" spacing={1}>
                {confidentWrongByQuestion.map((row) => (
                  <HStack
                    key={`wrong-${row.position}`}
                    justify="space-between"
                    bg="coral.50"
                    px={3}
                    py={2}
                    borderRadius="md"
                  >
                    <Text fontSize="sm">
                      Q{row.position}. {row.prompt}
                    </Text>
                    <Text fontSize="sm" fontWeight="600">
                      {row.count} response{row.count === 1 ? '' : 's'}
                    </Text>
                  </HStack>
                ))}
              </VStack>
            </Box>
          )}
          {facts.low_confidence_correct.length > 0 && (
            <Box>
              <Text fontSize="sm" fontWeight="700" color="cariteal.700" mb={2}>
                Correct but unsure ({facts.low_confidence_correct.length})
              </Text>
              <VStack align="stretch" spacing={1}>
                {unsureCorrectByQuestion.map((row) => (
                  <HStack
                    key={`unsure-${row.position}`}
                    justify="space-between"
                    bg="cariteal.50"
                    px={3}
                    py={2}
                    borderRadius="md"
                  >
                    <Text fontSize="sm">
                      Q{row.position}. {row.prompt}
                    </Text>
                    <Text fontSize="sm" fontWeight="600">
                      {row.count} response{row.count === 1 ? '' : 's'}
                    </Text>
                  </HStack>
                ))}
              </VStack>
            </Box>
          )}
        </VStack>
      </CardBody>
    </Card>
  );
}

function groupByQuestion(
  items: { question_position: number; question_prompt: string }[]
): { position: number; prompt: string; count: number }[] {
  const map = new Map<number, { prompt: string; count: number }>();
  for (const item of items) {
    const existing = map.get(item.question_position);
    if (existing) {
      existing.count += 1;
    } else {
      map.set(item.question_position, { prompt: item.question_prompt, count: 1 });
    }
  }
  return [...map.entries()]
    .sort(([a], [b]) => a - b)
    .map(([position, { prompt, count }]) => ({ position, prompt, count }));
}
