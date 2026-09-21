import { Box, HStack, Text, VStack } from '@chakra-ui/react';
import { FactBadge } from './FactBadge';

interface StatTileProps {
  label: string;
  value: string;
  help?: string;
  /** Marks the tile as a measured fact rather than a suggestion. */
  measured?: boolean;
  accent?: 'ocean' | 'cariteal' | 'coral' | 'gray';
}

const ACCENTS: Record<string, string> = {
  ocean: 'ocean.700',
  cariteal: 'cariteal.700',
  coral: 'coral.600',
  gray: 'gray.600',
};

export function StatTile({
  label,
  value,
  help,
  measured = true,
  accent = 'ocean',
}: StatTileProps) {
  return (
    <Box bg="white" borderWidth="1px" borderColor="sand.200" borderRadius="lg" p={4}>
      <VStack align="flex-start" spacing={1}>
        <HStack spacing={2}>
          <Text fontSize="xs" fontWeight="700" color="gray.600" textTransform="uppercase">
            {label}
          </Text>
          {measured && <FactBadge />}
        </HStack>
        <Text fontSize="2xl" fontWeight="800" color={ACCENTS[accent]} lineHeight="1.2">
          {value}
        </Text>
        {help && (
          <Text fontSize="sm" color="gray.600">
            {help}
          </Text>
        )}
      </VStack>
    </Box>
  );
}
