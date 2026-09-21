import { Box, HStack, Text } from '@chakra-ui/react';
import { confidenceLabel } from '@/utils/insightFormat';

interface ConfidenceScaleProps {
  name: string;
  legend: string;
  value: number | undefined;
  onChange: (value: number) => void;
  scale?: { min: number; max: number };
}

/**
 * The 1-5 confidence picker students tap.
 *
 * Native radio inputs inside a fieldset: arrow keys work, screen readers
 * announce the group, and the touch targets stay large at 360px without any
 * JavaScript beyond the state update.
 */
export function ConfidenceScale({
  name,
  legend,
  value,
  onChange,
  scale = { min: 1, max: 5 },
}: ConfidenceScaleProps) {
  const levels: number[] = [];
  for (let level = scale.min; level <= scale.max; level += 1) levels.push(level);

  return (
    <Box as="fieldset">
      <Text as="legend" fontSize="sm" fontWeight="600" color="gray.700" mb={2}>
        {legend}
      </Text>
      <HStack spacing={2} justify="space-between">
        {levels.map((level) => {
          const selected = value === level;
          return (
            <Box
              key={level}
              as="label"
              flex="1"
              cursor="pointer"
              borderWidth="1px"
              borderColor={selected ? 'ocean.600' : 'sand.300'}
              bg={selected ? 'ocean.600' : 'white'}
              color={selected ? 'white' : 'ocean.700'}
              borderRadius="md"
              py={3}
              textAlign="center"
              fontWeight="700"
              _focusWithin={{ boxShadow: 'outline' }}
            >
              <Box
                as="input"
                type="radio"
                name={name}
                value={level}
                checked={selected}
                onChange={() => onChange(level)}
                position="absolute"
                opacity={0}
                w="1px"
                h="1px"
                aria-label={confidenceLabel(level)}
              />
              {level}
            </Box>
          );
        })}
      </HStack>
      <HStack justify="space-between" mt={1}>
        <Text fontSize="xs" color="gray.600">
          Not sure
        </Text>
        <Text fontSize="xs" color="gray.600">
          Very sure
        </Text>
      </HStack>
    </Box>
  );
}
