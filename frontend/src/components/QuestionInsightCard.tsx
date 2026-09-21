import {
  Badge,
  Box,
  Card,
  CardBody,
  Flex,
  HStack,
  Progress,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
  VStack,
} from '@chakra-ui/react';
import type { QuestionInsight } from '@/api/types';
import { ConfidenceChart } from './ConfidenceChart';
import {
  correctnessTone,
  describeCorrectness,
  formatConfidence,
  formatPercent,
  questionTypeLabel,
  toneColorScheme,
  totalConfidenceResponses,
} from '@/utils/insightFormat';

export function QuestionInsightCard({ question }: { question: QuestionInsight }) {
  const tone = correctnessTone(question.correctness_percentage);
  const colorScheme = toneColorScheme(tone);
  const confidenceTotal = totalConfidenceResponses(question.confidence_distribution);

  return (
    <Card borderWidth="1px" borderColor="sand.200">
      <CardBody>
        <VStack align="stretch" spacing={4}>
          <Flex justify="space-between" align="flex-start" gap={3} wrap="wrap">
            <Box>
              <HStack spacing={2} mb={1}>
                <Badge colorScheme="ocean" variant="subtle">
                  Q{question.position}
                </Badge>
                <Text fontSize="xs" color="gray.600">
                  {questionTypeLabel(question.question_type)}
                </Text>
              </HStack>
              <Text fontWeight="700" color="ocean.800">
                {question.prompt}
              </Text>
            </Box>
            <VStack align="flex-end" spacing={0}>
              <Text fontSize="sm" color="gray.600">
                {question.response_count} response{question.response_count === 1 ? '' : 's'}
              </Text>
              <Text fontSize="sm" fontWeight="600" color={`${colorScheme}.700`}>
                {describeCorrectness(question)}
              </Text>
            </VStack>
          </Flex>

          {question.is_auto_scored && question.correctness_percentage !== null && (
            <Progress
              value={question.correctness_percentage}
              colorScheme={colorScheme}
              size="sm"
              borderRadius="full"
              aria-label={`Correctness for question ${question.position}`}
            />
          )}

          {question.choice_breakdown.length > 0 && (
            <Box overflowX="auto">
              <Table size="sm" variant="simple">
                <Thead>
                  <Tr>
                    <Th>Choice</Th>
                    <Th isNumeric>Picked</Th>
                    <Th isNumeric>Share</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {question.choice_breakdown.map((choice) => (
                    <Tr
                      key={choice.choice_id}
                      bg={choice.is_correct ? 'cariteal.50' : undefined}
                    >
                      <Td>
                        <HStack spacing={2}>
                          <Text>{choice.text}</Text>
                          {choice.is_correct && (
                            <Badge colorScheme="cariteal" variant="subtle" fontSize="0.6rem">
                              correct
                            </Badge>
                          )}
                        </HStack>
                      </Td>
                      <Td isNumeric>{choice.count}</Td>
                      <Td isNumeric>{formatPercent(choice.percentage)}</Td>
                    </Tr>
                  ))}
                </Tbody>
              </Table>
            </Box>
          )}

          {question.common_answers.length > 0 && (
            <Box>
              <Text fontSize="sm" fontWeight="700" color="gray.700" mb={2}>
                Most common answers
              </Text>
              <VStack align="stretch" spacing={1}>
                {question.common_answers.map((answer) => (
                  <HStack
                    key={answer.normalized}
                    justify="space-between"
                    bg="sand.100"
                    px={3}
                    py={2}
                    borderRadius="md"
                  >
                    <HStack spacing={2}>
                      <Text>{answer.answer}</Text>
                      {answer.matches_accepted === true && (
                        <Badge colorScheme="cariteal" variant="subtle" fontSize="0.6rem">
                          accepted
                        </Badge>
                      )}
                      {answer.matches_accepted === false && (
                        <Badge colorScheme="coral" variant="subtle" fontSize="0.6rem">
                          not accepted
                        </Badge>
                      )}
                    </HStack>
                    <Text fontSize="sm" color="gray.600">
                      {answer.count} · {formatPercent(answer.percentage)}
                    </Text>
                  </HStack>
                ))}
              </VStack>
            </Box>
          )}

          {confidenceTotal > 0 && (
            <Box>
              <HStack justify="space-between" mb={2}>
                <Text fontSize="sm" fontWeight="700" color="gray.700">
                  Confidence
                </Text>
                <Text fontSize="sm" color="gray.600">
                  Average {formatConfidence(question.average_confidence)}
                </Text>
              </HStack>
              <ConfidenceChart
                distribution={question.confidence_distribution}
                label={`Confidence for question ${question.position}`}
              />
            </Box>
          )}
        </VStack>
      </CardBody>
    </Card>
  );
}
