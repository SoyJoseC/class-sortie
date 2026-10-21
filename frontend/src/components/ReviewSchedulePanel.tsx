import { Badge, Box, Button, Flex, HStack, Stack, Text, useToast } from '@chakra-ui/react';
import { useNavigate } from 'react-router-dom';
import type { ReviewItem } from '@/api/types';
import { useCreateReviewActivityMutation, useSnoozeReviewItemMutation } from '@/api/caricueApi';
import { errorMessage } from '@/api/baseQuery';
import { formatDateTime, formatPercent } from '@/utils/insightFormat';

function boxLabel(box: number): string {
  if (box <= 0) return 'Just missed';
  if (box >= 5) return 'Well known';
  return `Box ${box}`;
}

export function ReviewSchedulePanel({
  items,
  compact = false,
}: {
  items: ReviewItem[];
  compact?: boolean;
}) {
  const navigate = useNavigate();
  const toast = useToast();
  const [createActivity, createState] = useCreateReviewActivityMutation();
  const [snooze, snoozeState] = useSnoozeReviewItemMutation();

  async function handleCreate(item: ReviewItem) {
    try {
      const result = await createActivity(item.id).unwrap();
      navigate(`/app/activities/${result.activity_id}`);
    } catch (err) {
      toast({ title: errorMessage(err, 'Could not draft a review.'), status: 'error' });
    }
  }

  async function handleSnooze(item: ReviewItem) {
    try {
      await snooze({ id: item.id, days: 1 }).unwrap();
      toast({ title: 'Snoozed until tomorrow', status: 'success', duration: 2500 });
    } catch (err) {
      toast({ title: errorMessage(err), status: 'error' });
    }
  }

  if (items.length === 0) {
    return (
      <Text fontSize="sm" color="gray.600">
        Nothing is due. Topics move to the next box when the class scores 80% or more, stay put
        between 60% and 79%, and go back to the start below 60% or when someone is confidently
        wrong.
      </Text>
    );
  }

  return (
    <Stack spacing={3}>
      {!compact && (
        <Text fontSize="sm" color="gray.600">
          One card per topic for the class — not per student, so it works even when they join
          with a name. The gaps are 1, 3, 7, 14, 30 and 60 days.
        </Text>
      )}
      {items.map((item) => (
        <Flex
          key={item.id}
          justify="space-between"
          align="flex-start"
          gap={3}
          wrap="wrap"
          bg={item.is_due ? 'coral.50' : 'sand.100'}
          px={3}
          py={2}
          borderRadius="md"
        >
          <Box>
            <HStack spacing={2} mb={1}>
              <Text fontWeight="700" color="ocean.800">
                {item.topic_label}
              </Text>
              <Badge colorScheme={item.is_due ? 'coral' : 'gray'} variant="subtle">
                {boxLabel(item.box)}
              </Badge>
            </HStack>
            <Text fontSize="sm" color="gray.600">
              {item.classroom_name}
              {item.last_score != null ? ` · last ${formatPercent(item.last_score)}` : ''}
              {item.last_session_code ? ` · session ${item.last_session_code}` : ''}
            </Text>
            <Text fontSize="xs" color="gray.600">
              {item.is_due ? 'Due now' : `Next check ${formatDateTime(item.due_at)}`}
              {` · then wait ${item.interval_days} day${item.interval_days === 1 ? '' : 's'}`}
            </Text>
          </Box>
          <HStack>
            <Button
              size="sm"
              variant="outline"
              onClick={() => void handleSnooze(item)}
              isLoading={snoozeState.isLoading}
            >
              Snooze 1 day
            </Button>
            <Button
              size="sm"
              variant="accent"
              onClick={() => void handleCreate(item)}
              isLoading={createState.isLoading}
            >
              Draft review
            </Button>
          </HStack>
        </Flex>
      ))}
    </Stack>
  );
}
