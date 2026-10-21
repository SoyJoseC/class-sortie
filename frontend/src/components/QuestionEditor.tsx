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
import type { ActivityKind, Question, QuestionType } from '@/api/types';
import {
  MAX_CHOICES,
  QUESTION_TYPES_BY_KIND,
  blankChoice,
  changeQuestionType,
  formatAcceptedAnswers,
  hasChoices,
  parseAcceptedAnswers,
  yesNoChoices,
} from '@/utils/activityDraft';
import { questionTypeLabel } from '@/utils/insightFormat';
import { QuestionImageField } from './QuestionImageField';

interface QuestionEditorProps {
  question: Question;
  index: number;
  total: number;
  error?: string;
  /** A survey is unmarked: no answer key, no confidence, extra question types. */
  kind?: ActivityKind;
  onChange: (question: Question) => void;
  onRemove: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
}

export function QuestionEditor({
  question,
  index,
  total,
  error,
  kind = 'quiz',
  onChange,
  onRemove,
  onMoveUp,
  onMoveDown,
}: QuestionEditorProps) {
  const promptId = `question-${index}-prompt`;
  const typeId = `question-${index}-type`;
  const survey = kind === 'survey';
  const hasAnswerKey = !survey && question.question_type === 'multiple_choice';

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
                {questionTypeLabel(question.question_type, kind)}
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

          <QuestionImageField question={question} index={index} onChange={onChange} />

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
                {QUESTION_TYPES_BY_KIND[kind].map((type: QuestionType) => (
                  <option key={type} value={type}>
                    {questionTypeLabel(type, kind)}
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

            {!survey && question.question_type !== 'confidence' && (
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

          {hasChoices(question.question_type) && (
            <Box>
              <Text fontWeight="600" fontSize="sm" mb={2}>
                {hasAnswerKey
                  ? 'Choices — tick the correct one(s)'
                  : question.question_type === 'multi_select'
                    ? 'Choices — students can tick more than one'
                    : 'Choices'}
              </Text>
              <Stack spacing={2}>
                {question.choices.map((choice, choiceIndex) => (
                  <HStack key={choiceIndex} spacing={2}>
                    {hasAnswerKey && (
                      <Checkbox
                        isChecked={choice.is_correct}
                        onChange={(e) =>
                          updateChoice(choiceIndex, { is_correct: e.target.checked })
                        }
                        colorScheme="cariteal"
                        aria-label={`Choice ${choiceIndex + 1} of question ${index + 1} is correct`}
                      />
                    )}
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
              <HStack mt={2} spacing={2} wrap="wrap">
                <Button
                  size="sm"
                  variant="outline"
                  isDisabled={question.choices.length >= MAX_CHOICES}
                  onClick={() =>
                    onChange({ ...question, choices: [...question.choices, blankChoice()] })
                  }
                >
                  Add choice
                </Button>
                {survey && question.question_type === 'multiple_choice' && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => onChange({ ...question, choices: yesNoChoices() })}
                  >
                    Use Yes / No
                  </Button>
                )}
              </HStack>
            </Box>
          )}

          {question.question_type === 'rating' && (
            <Box>
              <Text fontWeight="600" fontSize="sm" mb={2}>
                Students pick a number from 1 to 5
              </Text>
              <HStack spacing={3} align="flex-end" wrap="wrap">
                <FormControl maxW="12rem">
                  <FormLabel htmlFor={`question-${index}-low`} fontSize="sm">
                    Label for 1 (optional)
                  </FormLabel>
                  <Input
                    id={`question-${index}-low`}
                    value={question.rating_low_label ?? ''}
                    onChange={(e) =>
                      onChange({ ...question, rating_low_label: e.target.value })
                    }
                    placeholder="e.g. Strongly disagree"
                    maxLength={60}
                  />
                </FormControl>
                <HStack spacing={2} pb={1}>
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
                    >
                      {level}
                    </Box>
                  ))}
                </HStack>
                <FormControl maxW="12rem">
                  <FormLabel htmlFor={`question-${index}-high`} fontSize="sm">
                    Label for 5 (optional)
                  </FormLabel>
                  <Input
                    id={`question-${index}-high`}
                    value={question.rating_high_label ?? ''}
                    onChange={(e) =>
                      onChange({ ...question, rating_high_label: e.target.value })
                    }
                    placeholder="e.g. Strongly agree"
                    maxLength={60}
                  />
                </FormControl>
              </HStack>
            </Box>
          )}

          {!survey && question.question_type === 'short_text' && (
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
