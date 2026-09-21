import { Box, HStack, Text, VStack } from '@chakra-ui/react';
import { TAGLINE } from '@/theme';

interface BrandProps {
  showTagline?: boolean;
  size?: 'sm' | 'md' | 'lg';
  /** `light` is for placement on the deep-ocean header of the student pages. */
  variant?: 'default' | 'light';
}

/** The CariCue wordmark: a simple wave glyph plus the name. */
export function Brand({ showTagline = false, size = 'md', variant = 'default' }: BrandProps) {
  const nameSize = size === 'lg' ? '2xl' : size === 'sm' ? 'md' : 'xl';
  const glyph = size === 'lg' ? 12 : size === 'sm' ? 7 : 9;
  const isLight = variant === 'light';

  return (
    <HStack spacing={3} align="center">
      <Box
        as="svg"
        viewBox="0 0 32 32"
        width={`${glyph * 4}px`}
        height={`${glyph * 4}px`}
        aria-hidden="true"
        flexShrink={0}
      >
        <circle cx="16" cy="16" r="15" fill={isLight ? '#FFFFFF' : '#0B3C5D'} />
        <path
          d="M4 20c3 0 4.5-3 7.5-3s4.5 3 7.5 3 4.5-3 7.5-3"
          stroke="#17A398"
          strokeWidth="2.5"
          fill="none"
          strokeLinecap="round"
        />
        <circle cx="16" cy="11" r="2.5" fill="#E26244" />
      </Box>
      <VStack spacing={0} align="flex-start">
        <Text
          fontSize={nameSize}
          fontWeight="800"
          color={isLight ? 'white' : 'ocean.700'}
          lineHeight="1.1"
          letterSpacing="-0.02em"
        >
          CariCue
        </Text>
        {showTagline && (
          <Text
            fontSize="xs"
            color={isLight ? 'cariteal.200' : 'cariteal.700'}
            fontWeight="600"
          >
            {TAGLINE}
          </Text>
        )}
      </VStack>
    </HStack>
  );
}
