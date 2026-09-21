import { Box, HStack, Text, VStack } from '@chakra-ui/react';
import type { ConfidenceDistribution } from '@/api/types';
import {
  confidenceBars,
  confidenceLabel,
  totalConfidenceResponses,
} from '@/utils/insightFormat';

/**
 * Confidence distribution as a horizontal bar chart.
 *
 * Built from divs rather than a charting library: it is five bars, it must
 * render on a slow connection, and a table-like accessible structure is more
 * useful to a screen reader than an SVG chart.
 */
export function ConfidenceChart({
  distribution,
  compact = false,
  label = 'Confidence distribution',
}: {
  distribution: ConfidenceDistribution | undefined;
  compact?: boolean;
  label?: string;
}) {
  const bars = confidenceBars(distribution);
  const total = totalConfidenceResponses(distribution);

  if (total === 0) {
    return (
      <Text fontSize="sm" color="gray.600">
        No confidence ratings collected.
      </Text>
    );
  }

  return (
    <VStack
      spacing={compact ? 1 : 2}
      align="stretch"
      as="ul"
      listStyleType="none"
      ml={0}
      aria-label={label}
    >
      {bars.map((bar) => (
        <HStack as="li" key={bar.level} spacing={3}>
          <Text
            fontSize="sm"
            fontWeight="700"
            color="ocean.700"
            minW="1.5rem"
            textAlign="right"
            aria-hidden="true"
          >
            {bar.level}
          </Text>
          <Box flex="1" bg="sand.200" borderRadius="full" h={compact ? '8px' : '12px'}>
            <Box
              bg={bar.level >= 4 ? 'cariteal.600' : bar.level === 3 ? 'ocean.400' : 'coral.500'}
              h="100%"
              borderRadius="full"
              width={`${bar.percentage}%`}
              transition="width 0.4s ease"
            />
          </Box>
          <Text fontSize="sm" color="gray.700" minW="4.5rem">
            <Box as="span" srOnly>
              {confidenceLabel(bar.level)}:{' '}
            </Box>
            {bar.count} ({bar.percentage.toFixed(0)}%)
          </Text>
        </HStack>
      ))}
    </VStack>
  );
}
