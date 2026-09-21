import {
  Box,
  Button,
  Card,
  CardBody,
  Heading,
  HStack,
  Stack,
  Text,
  useToast,
  VStack,
} from '@chakra-ui/react';
import { useNavigate } from 'react-router-dom';
import type { MisconceptionCard } from '@/api/types';
import { useCreateFollowUpActivityMutation } from '@/api/caricueApi';
import { errorMessage } from '@/api/baseQuery';
import { FactBadge, SuggestionBadge } from '@/components/FactBadge';

export interface MisconceptionCardActions {
  onUseInReflection?: (card: MisconceptionCard) => void;
}

export function MisconceptionCardPanel({
  sessionId,
  cards,
  actions,
  showBulkFollowUp = false,
}: {
  sessionId: number;
  cards: MisconceptionCard[];
  actions?: MisconceptionCardActions;
  showBulkFollowUp?: boolean;
}) {
  const toast = useToast();
  const navigate = useNavigate();
  const [createFollowUp, followUpState] = useCreateFollowUpActivityMutation();

  if (cards.length === 0) return null;

  async function handleCreateFollowUp(questionIds?: number[]) {
    try {
      const result = await createFollowUp({
        sessionId,
        question_ids: questionIds,
        include_confidence: true,
      }).unwrap();
      toast({
        title: 'Follow-up draft created',
        description: 'Review and edit the questions before launching.',
        status: 'success',
      });
      navigate(`/app/activities/${result.activity_id}`);
    } catch (err) {
      toast({ title: errorMessage(err), status: 'error' });
    }
  }

  function copyTalkingPoint(card: MisconceptionCard) {
    const text = card.suggestion?.body ?? '';
    void navigator.clipboard.writeText(text);
    toast({ title: 'Talking point copied', status: 'success', duration: 2000 });
  }

  return (
    <Card borderWidth="1px" borderColor="coral.200" bg="white">
      <CardBody>
        <HStack justify="space-between" mb={3} wrap="wrap" gap={2}>
          <Heading size="sm" color="ocean.800">
            Misconception cards
          </Heading>
          {showBulkFollowUp && (
            <Button
              size="sm"
              variant="accent"
              onClick={() => void handleCreateFollowUp()}
              isLoading={followUpState.isLoading}
            >
              Create follow-up from this session
            </Button>
          )}
        </HStack>
        <VStack spacing={4} align="stretch">
          {cards.map((card) => (
            <Box
              key={card.question_id}
              borderWidth="1px"
              borderColor="sand.200"
              borderRadius="md"
              p={4}
              bg="sand.50"
            >
              <Text fontWeight="700" fontSize="sm" color="ocean.800" mb={1}>
                Q{card.position}. {card.prompt}
              </Text>
              <Stack spacing={2} mb={3}>
                {card.facts.map((fact) => (
                  <HStack key={fact.label} justify="space-between" fontSize="sm">
                    <HStack>
                      <FactBadge />
                      <Text color="gray.700">{fact.label}</Text>
                    </HStack>
                    <Text fontWeight="600">{String(fact.value)}</Text>
                  </HStack>
                ))}
              </Stack>
              {card.suggestion && (
                <Box mb={3}>
                  <HStack mb={1}>
                    <SuggestionBadge />
                    <Text fontSize="sm" fontWeight="600">
                      {card.suggestion.title}
                    </Text>
                  </HStack>
                  <Text fontSize="sm" color="gray.700">
                    {card.suggestion.body}
                  </Text>
                </Box>
              )}
              <HStack spacing={2} wrap="wrap">
                {card.suggestion && (
                  <Button size="xs" variant="outline" onClick={() => copyTalkingPoint(card)}>
                    Copy talking point
                  </Button>
                )}
                {actions?.onUseInReflection && card.suggestion && (
                  <Button
                    size="xs"
                    variant="outline"
                    onClick={() => actions.onUseInReflection?.(card)}
                  >
                    Use in reflection
                  </Button>
                )}
                <Button
                  size="xs"
                  variant="accent"
                  onClick={() => void handleCreateFollowUp([card.question_id])}
                  isLoading={followUpState.isLoading}
                >
                  Create follow-up
                </Button>
              </HStack>
            </Box>
          ))}
        </VStack>
      </CardBody>
    </Card>
  );
}
