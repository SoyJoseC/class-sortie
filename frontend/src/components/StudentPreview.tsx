import {
  Box,
  Card,
  CardBody,
  Heading,
  HStack,
  Radio,
  Textarea,
  RadioGroup,
  Stack,
  Text,
  VStack,
} from '@chakra-ui/react';
import type { Question } from '@/api/types';

/**
 * Renders the activity the way a student will see it on a phone.
 *
 * Deliberately non-interactive and built from the draft in memory, so the
 * teacher can check wording without saving. Correct answers are never shown
 * here, matching what the public endpoint actually returns.
 */
export function StudentPreview({
  title,
  topic,
  questions,
}: {
  title: string;
  topic: string;
  questions: Question[];
}) {
  return (
    <Box
      maxW="360px"
      mx="auto"
      bg="sand.50"
      borderWidth="8px"
      borderColor="ocean.800"
      borderRadius="2xl"
      p={3}
      aria-label="Student preview"
    >
      <VStack align="stretch" spacing={3}>
        <Box>
          <Heading size="sm" color="ocean.800">
            {title || 'Untitled activity'}
          </Heading>
          {topic && (
            <Text fontSize="xs" color="cariteal.700">
              {topic}
            </Text>
          )}
        </Box>

        {questions.length === 0 && (
          <Text fontSize="sm" color="gray.600">
            Add a question to see the student view.
          </Text>
        )}

        {questions.map((question, index) => (
          <Card key={index} size="sm" borderWidth="1px" borderColor="sand.200">
            <CardBody>
              <VStack align="stretch" spacing={2}>
                <Text fontSize="sm" fontWeight="700" color="ocean.800">
                  {index + 1}. {question.prompt || 'Question prompt'}
                  {!question.is_required && (
                    <Text as="span" fontWeight="400" color="gray.500">
                      {' '}
                      (optional)
                    </Text>
                  )}
                </Text>

                {question.question_type === 'multiple_choice' && (
                  <RadioGroup value="" onChange={() => undefined}>
                    <Stack spacing={1}>
                      {question.choices
                        .filter((choice) => choice.text.trim())
                        .map((choice, choiceIndex) => (
                          <Radio
                            key={choiceIndex}
                            value={String(choiceIndex)}
                            isDisabled
                            size="sm"
                          >
                            <Text fontSize="sm">{choice.text}</Text>
                          </Radio>
                        ))}
                    </Stack>
                  </RadioGroup>
                )}

                {question.question_type === 'short_text' && (
                  <Textarea
                    size="sm"
                    placeholder="Type your answer"
                    rows={3}
                    isDisabled
                    resize="none"
                  />
                )}

                {(question.question_type === 'confidence' || question.collect_confidence) && (
                  <Box>
                    <Text fontSize="xs" color="gray.600" mb={1}>
                      How confident are you?
                    </Text>
                    <HStack spacing={2}>
                      {[1, 2, 3, 4, 5].map((level) => (
                        <Box
                          key={level}
                          w="32px"
                          h="32px"
                          borderWidth="1px"
                          borderColor="sand.300"
                          borderRadius="md"
                          display="flex"
                          alignItems="center"
                          justifyContent="center"
                          fontSize="sm"
                          color="ocean.700"
                        >
                          {level}
                        </Box>
                      ))}
                    </HStack>
                  </Box>
                )}
              </VStack>
            </CardBody>
          </Card>
        ))}

        <Box
          bg="coral.600"
          color="white"
          textAlign="center"
          py={2}
          borderRadius="md"
          fontWeight="700"
          fontSize="sm"
        >
          Submit answers
        </Box>
      </VStack>
    </Box>
  );
}
