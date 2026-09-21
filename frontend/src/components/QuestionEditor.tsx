import {
  Badge,
  Box,
  Button,
  Card,
  CardBody,
  Checkbox,
  Flex,
  FormControl,
  FormErrorMessage,
  FormHelperText,
  FormLabel,
  HStack,
  IconButton,
  Input,
  Radio,
  RadioGroup,
  Select,
  Stack,
  Switch,
  Text,
  Textarea,
  Tooltip,
  VStack,
} from '@chakra-ui/react';
import type { Question, QuestionType } from '@/api/types';
import {
  MAX_CHOICES,
  blankChoice,
  changeQuestionType,
  formatAcceptedAnswers,
  parseAcceptedAnswers,
} from '@/utils/activityDraft';
import { questionTypeLabel } from '@/utils/insightFormat';

interface QuestionEditorProps {
  question: Question;
  index: number;
  total: number;
  error?: string;
  onChange: (question: Question) => void;
  onRemove: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
}

const TYPE_OPTIONS: QuestionType[] = ['multiple_choice', 'short_text', 'confidence'];

export function QuestionEditor({
  question,
  index,
  total,
  error,
  onChange,
  onRemove,
  onMoveUp,
  onMoveDown,
}: QuestionEditorProps) {
  const promptId = `question-${index}-prompt`;
  const typeId = `question-${index}-type`;

  function updateChoice(
    choiceIndex: number,
    patch: Partial<{ text: string; is_correct: boolean }>
  ) {
    const choices = question.choices.map((choice, i) =>
      i === choiceIndex ? { ...choice, ...patch } : choice
    );
    onChange({ ...question, choices });
  }

  return (
    <Card
      borderWidth="1px"
      borderColor={error ? 'coral.400' : 'sand.200'}
      as="fieldset"
      aria-label={`Question ${index + 1}`}
    >
      <CardBody>
        <VStack align="stretch" spacing={4}>
          <Flex justify="space-between" align="center" gap={2} wrap="wrap">
            <HStack>
              <Badge colorScheme="ocean" variant="solid" fontSize="0.7rem">
                Question {index + 1}
              </Badge>
              <Text fontSize="sm" color="gray.600">
                {questionTypeLabel(question.question_type)}
              </Text>
            </HStack>
            <HStack spacing={1}>
              <Tooltip label="Move up" hasArrow>
                <IconButton
                  aria-label={`Move question ${index + 1} up`}
                  size="sm"
                  variant="ghost"
                  isDisabled={index === 0}
                  onClick={onMoveUp}
                  icon={<Box aria-hidden="true">↑</Box>}
                />
              </Tooltip>
              <Tooltip label="Move down" hasArrow>
                <IconButton
                  aria-label={`Move question ${index + 1} down`}
                  size="sm"
                  variant="ghost"
                  isDisabled={index === total - 1}
                  onClick={onMoveDown}
                  icon={<Box aria-hidden="true">↓</Box>}
                />
              </Tooltip>
              <Tooltip label="Remove question" hasArrow>
                <IconButton
                  aria-label={`Remove question ${index + 1}`}
                  size="sm"
                  variant="ghost"
                  colorScheme="coral"
                  onClick={onRemove}
                  icon={<Box aria-hidden="true">✕</Box>}
                />
              </Tooltip>
            </HStack>
          </Flex>

          <FormControl isInvalid={Boolean(error)}>
            <FormLabel htmlFor={promptId}>Prompt</FormLabel>
            <Textarea
              id={promptId}
              value={question.prompt}
              onChange={(e) => onChange({ ...question, prompt: e.target.value })}
              placeholder="Which device routes traffic between two networks?"
              rows={2}
            />
            <FormErrorMessage>{error}</FormErrorMessage>
          </FormControl>

          <HStack align="flex-end" spacing={4} wrap="wrap">
            <FormControl maxW="16rem">
              <FormLabel htmlFor={typeId}>Question type</FormLabel>
              <Select
                id={typeId}
                value={question.question_type}
                onChange={(e) =>
                  onChange(changeQuestionType(question, e.target.value as QuestionType))
                }
              >
                {TYPE_OPTIONS.map((type) => (
                  <option key={type} value={type}>
                    {questionTypeLabel(type)}
                  </option>
                ))}
              </Select>
            </FormControl>

            <FormControl display="flex" alignItems="center" w="auto">
              <Switch
                id={`question-${index}-required`}
                isChecked={question.is_required}
                onChange={(e) => onChange({ ...question, is_required: e.target.checked })}
                colorScheme="cariteal"
                mr={2}
              />
              <FormLabel htmlFor={`question-${index}-required`} mb={0} fontSize="sm">
                Required
              </FormLabel>
            </FormControl>

            {question.question_type !== 'confidence' && (
              <FormControl display="flex" alignItems="center" w="auto">
                <Switch
                  id={`question-${index}-confidence`}
                  isChecked={question.collect_confidence}
                  onChange={(e) =>
                    onChange({ ...question, collect_confidence: e.target.checked })
                  }
                  colorScheme="cariteal"
                  mr={2}
                />
                <FormLabel htmlFor={`question-${index}-confidence`} mb={0} fontSize="sm">
                  Ask for confidence (1-5)
                </FormLabel>
              </FormControl>
            )}
          </HStack>

          {question.question_type === 'multiple_choice' && (
            <Box>
              <Text fontWeight="600" fontSize="sm" mb={2}>
                Choices — tick the correct one(s)
              </Text>
              <Stack spacing={2}>
                {question.choices.map((choice, choiceIndex) => (
                  <HStack key={choiceIndex} spacing={2}>
                    <Checkbox
                      isChecked={choice.is_correct}
                      onChange={(e) =>
                        updateChoice(choiceIndex, { is_correct: e.target.checked })
                      }
                      colorScheme="cariteal"
                      aria-label={`Choice ${choiceIndex + 1} of question ${index + 1} is correct`}
                    />
                    <Input
                      value={choice.text}
                      onChange={(e) => updateChoice(choiceIndex, { text: e.target.value })}
                      placeholder={`Choice ${choiceIndex + 1}`}
                      aria-label={`Choice ${choiceIndex + 1} text for question ${index + 1}`}
                    />
                    <IconButton
                      aria-label={`Remove choice ${choiceIndex + 1} from question ${index + 1}`}
                      size="sm"
                      variant="ghost"
                      colorScheme="coral"
                      isDisabled={question.choices.length <= 2}
                      onClick={() =>
                        onChange({
                          ...question,
                          choices: question.choices.filter((_, i) => i !== choiceIndex),
                        })
                      }
                      icon={<Box aria-hidden="true">✕</Box>}
                    />
                  </HStack>
                ))}
              </Stack>
              <Button
                mt={2}
                size="sm"
                variant="outline"
                isDisabled={question.choices.length >= MAX_CHOICES}
                onClick={() =>
                  onChange({ ...question, choices: [...question.choices, blankChoice()] })
                }
              >
                Add choice
              </Button>
            </Box>
          )}

          {question.question_type === 'short_text' && (
            <FormControl>
              <FormLabel htmlFor={`question-${index}-accepted`}>
                Accepted answers (optional, one per line)
              </FormLabel>
              <Textarea
                id={`question-${index}-accepted`}
                value={formatAcceptedAnswers(question.accepted_answers)}
                onChange={(e) =>
                  onChange({
                    ...question,
                    accepted_answers: parseAcceptedAnswers(e.target.value),
                  })
                }
                placeholder={'Random Access Memory\nRAM'}
                rows={3}
              />
              <FormHelperText>
                {question.accepted_answers.length > 0
                  ? 'Answers are matched after trimming spaces and ignoring capitalisation. Nothing else — no spelling correction, no AI grading.'
                  : 'Leave empty to keep this question unscored. You will read the responses yourself.'}
              </FormHelperText>
            </FormControl>
          )}

          {question.question_type === 'confidence' && (
            <Box bg="sand.100" p={3} borderRadius="md">
              <Text fontSize="sm" color="gray.700" mb={2}>
                Students will see a 1-5 scale. This question is never marked right or wrong.
              </Text>
              <RadioGroup value="" onChange={() => undefined}>
                <HStack spacing={4}>
                  {[1, 2, 3, 4, 5].map((level) => (
                    <Radio key={level} value={String(level)} isReadOnly isDisabled>
                      {level}
                    </Radio>
                  ))}
                </HStack>
              </RadioGroup>
            </Box>
          )}
        </VStack>
      </CardBody>
    </Card>
  );
}
