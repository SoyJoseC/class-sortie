import { Badge, Box, Card, CardBody, Heading, HStack, Text, VStack } from '@chakra-ui/react';
import type { SessionFacts } from '@/api/types';
import { FactBadge } from './FactBadge';
import {
  describeAttention,
  formatConfidence,
  formatPercent,
  hasPerformanceConfidenceSignal,
} from '@/utils/insightFormat';

/** Participants the arithmetic flags, plus the confidence-versus-score signals. */
export function AttentionPanel({ facts }: { facts: SessionFacts }) {
  const showSignals = hasPerformanceConfidenceSignal(facts);

  return (
    <VStack align="stretch" spacing={4}>
      <Card borderWidth="1px" borderColor="sand.200">
        <CardBody>
          <HStack justify="space-between" mb={3}>
            <Heading size="sm" color="ocean.800">
              May need attention
            </Heading>
            <FactBadge />
          </HStack>

          {facts.needs_attention.length === 0 ? (
            <Text fontSize="sm" color="gray.600">
              No one stands out yet. This list fills in as scored answers arrive.
            </Text>
          ) : (
            <VStack align="stretch" spacing={2}>
              {facts.needs_attention.map((item) => (
                <Box
                  key={item.participant_id}
                  borderWidth="1px"
                  borderColor="sand.200"
                  borderRadius="md"
                  p={3}
                >
                  <HStack justify="space-between" wrap="wrap" gap={2}>
                    <Text fontWeight="700" color="ocean.800">
                      {item.label}
                    </Text>
                    <HStack spacing={2}>
                      <Badge colorScheme="coral" variant="subtle">
                        {formatPercent(item.score_percentage)} correct
                      </Badge>
                      <Badge colorScheme="ocean" variant="subtle">
                        {formatConfidence(item.average_confidence)}
                      </Badge>
                    </HStack>
                  </HStack>
                  <Text fontSize="sm" color="gray.700" mt={1}>
                    {describeAttention(item)}
                  </Text>
                </Box>
              ))}
            </VStack>
          )}
        </CardBody>
      </Card>

      {showSignals && (
        <Card borderWidth="1px" borderColor="sand.200">
          <CardBody>
            <HStack justify="space-between" mb={3}>
              <Heading size="sm" color="ocean.800">
                Performance versus confidence
              </Heading>
              <FactBadge />
            </HStack>

            <VStack align="stretch" spacing={4}>
              {facts.high_confidence_incorrect.length > 0 && (
                <Box>
                  <Text fontSize="sm" fontWeight="700" color="coral.700" mb={1}>
                    Confident but wrong ({facts.high_confidence_incorrect.length})
                  </Text>
                  <Text fontSize="xs" color="gray.600" mb={2}>
                    The strongest single signal of a misconception worth addressing.
                  </Text>
                  <VStack align="stretch" spacing={1}>
                    {facts.high_confidence_incorrect.map((item, index) => (
                      <HStack
                        key={`${item.participant_id}-${item.question_position}-${index}`}
                        justify="space-between"
                        bg="coral.50"
                        px={3}
                        py={2}
                        borderRadius="md"
                      >
                        <Text fontSize="sm">
                          <Text as="span" fontWeight="700">
                            {item.label}
                          </Text>{' '}
                          — Q{item.question_position}
                        </Text>
                        <Text fontSize="sm" color="gray.700">
                          confidence {item.confidence_value}/5
                        </Text>
                      </HStack>
                    ))}
                  </VStack>
                </Box>
              )}

              {facts.low_confidence_correct.length > 0 && (
                <Box>
                  <Text fontSize="sm" fontWeight="700" color="cariteal.700" mb={1}>
                    Correct but unsure ({facts.low_confidence_correct.length})
                  </Text>
                  <Text fontSize="xs" color="gray.600" mb={2}>
                    Usually a cue to reinforce rather than reteach.
                  </Text>
                  <VStack align="stretch" spacing={1}>
                    {facts.low_confidence_correct.map((item, index) => (
                      <HStack
                        key={`${item.participant_id}-${item.question_position}-${index}`}
                        justify="space-between"
                        bg="cariteal.50"
                        px={3}
                        py={2}
                        borderRadius="md"
                      >
                        <Text fontSize="sm">
                          <Text as="span" fontWeight="700">
                            {item.label}
                          </Text>{' '}
                          — Q{item.question_position}
                        </Text>
                        <Text fontSize="sm" color="gray.700">
                          confidence {item.confidence_value}/5
                        </Text>
                      </HStack>
                    ))}
                  </VStack>
                </Box>
              )}
            </VStack>
          </CardBody>
        </Card>
      )}
    </VStack>
  );
}
