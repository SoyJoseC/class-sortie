import {
  Alert,
  AlertIcon,
  Badge,
  Box,
  Card,
  CardBody,
  Heading,
  HStack,
  Link,
  Stack,
  Text,
  VStack,
} from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';
import type { SessionComparison } from '@/api/types';
import { FactBadge } from '@/components/FactBadge';
import { formatDateTime, formatPercent } from '@/utils/insightFormat';

export function SessionComparisonPanel({
  comparison,
  classroomId,
}: {
  comparison: SessionComparison;
  classroomId?: number;
}) {
  const baseline = comparison.baseline_snapshot;
  if (!baseline) return null;

  const delta = comparison.overall_delta;
  const deltaLabel =
    delta === null
      ? '—'
      : delta > 0
        ? `+${delta.toFixed(1)}%`
        : `${delta.toFixed(1)}%`;
  const deltaColor = delta === null ? 'gray' : delta >= 0 ? 'cariteal' : 'coral';

  return (
    <Card borderWidth="1px" borderColor="cariteal.200" bg="cariteal.50">
      <CardBody>
        <HStack justify="space-between" mb={3}>
          <Heading size="sm" color="ocean.800">
            Did reteach work?
          </Heading>
          <FactBadge />
        </HStack>

        <Stack spacing={3}>
          <Box>
            <Text fontSize="sm" color="gray.600">
              Compared to session {baseline.session_code}
              {baseline.closed_at ? ` · ${formatDateTime(baseline.closed_at)}` : ''}
            </Text>
            {baseline.primary_gap && (
              <Text fontSize="sm" mt={1} fontStyle="italic" color="gray.700">
                &ldquo;{baseline.primary_gap}&rdquo;
              </Text>
            )}
            {baseline.planned_action && (
              <Text fontSize="sm" color="gray.600">
                Planned: {baseline.planned_action}
              </Text>
            )}
          </Box>

          <HStack spacing={4}>
            <Box>
              <Text fontSize="xs" color="gray.600">
                Baseline correct
              </Text>
              <Text fontWeight="700">{formatPercent(baseline.overall_correctness)}</Text>
            </Box>
            <Box>
              <Text fontSize="xs" color="gray.600">
                Overall change
              </Text>
              <Badge colorScheme={deltaColor} fontSize="md" px={2}>
                {deltaLabel}
              </Badge>
            </Box>
          </HStack>

          {comparison.question_deltas.length > 0 && (
            <Box>
              <Text fontSize="sm" fontWeight="600" mb={2}>
                Question changes
              </Text>
              <VStack align="stretch" spacing={2}>
                {comparison.question_deltas.map((qd) => (
                  <HStack
                    key={`${qd.baseline_position}-${qd.current_position}`}
                    justify="space-between"
                    bg="white"
                    px={3}
                    py={2}
                    borderRadius="md"
                    fontSize="sm"
                  >
                    <Text>
                      Q{qd.baseline_position} → Q{qd.current_position}
                    </Text>
                    <HStack>
                      <Text color="gray.600">
                        {formatPercent(qd.baseline_correctness)} →{' '}
                        {formatPercent(qd.current_correctness)}
                      </Text>
                      {qd.delta !== null && (
                        <Badge
                          colorScheme={qd.delta >= 0 ? 'cariteal' : 'coral'}
                          variant="subtle"
                        >
                          {qd.delta > 0 ? '+' : ''}
                          {qd.delta}%
                        </Badge>
                      )}
                    </HStack>
                  </HStack>
                ))}
              </VStack>
            </Box>
          )}

          {comparison.alignment === 'partial' && comparison.question_deltas.length === 0 && (
            <Text fontSize="sm" color="gray.600">
              Per-question comparison unavailable — activities differ in structure.
            </Text>
          )}

          {comparison.tracking_mode === 'class_only' && (
            <Alert status="info" borderRadius="md" fontSize="sm">
              <AlertIcon />
              <Box>
                Student movement tracking requires roster identifier join mode.{' '}
                {classroomId && (
                  <Link as={RouterLink} to={`/app/classes/${classroomId}`} color="ocean.700">
                    Review class settings
                  </Link>
                )}
              </Box>
            </Alert>
          )}

          {comparison.tracking_mode === 'roster' && comparison.student_movement && (
            <Box>
              <Text fontSize="sm" fontWeight="600" mb={2}>
                Student movement
              </Text>
              {comparison.student_movement.improved.length > 0 && (
                <Box mb={2}>
                  <Text fontSize="xs" color="gray.600" mb={1}>
                    Improved ({comparison.student_movement.improved_count})
                  </Text>
                  <Text fontSize="sm">
                    {comparison.student_movement.improved.map((s) => s.label).join(', ')}
                    {comparison.student_movement.improved_count >
                      comparison.student_movement.improved.length &&
                      ` +${comparison.student_movement.improved_count - comparison.student_movement.improved.length} more`}
                  </Text>
                </Box>
              )}
              {comparison.student_movement.still_stuck.length > 0 && (
                <Box>
                  <Text fontSize="xs" color="gray.600" mb={1}>
                    Still stuck ({comparison.student_movement.still_stuck_count})
                  </Text>
                  <Text fontSize="sm">
                    {comparison.student_movement.still_stuck.map((s) => s.label).join(', ')}
                    {comparison.student_movement.still_stuck_count >
                      comparison.student_movement.still_stuck.length &&
                      ` +${comparison.student_movement.still_stuck_count - comparison.student_movement.still_stuck.length} more`}
                  </Text>
                </Box>
              )}
            </Box>
          )}
        </Stack>
      </CardBody>
    </Card>
  );
}
