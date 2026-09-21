import { Badge, Tooltip } from '@chakra-ui/react';

/**
 * The visual contract between measured data and AI advice.
 *
 * Every number on the results screens is either a `fact` (arithmetic over
 * stored responses) or a `suggestion` (advisory text from an insight
 * provider). These two badges must never be used interchangeably.
 */

export function FactBadge() {
  return (
    <Tooltip label="Calculated directly from student responses." hasArrow>
      <Badge
        colorScheme="cariteal"
        variant="subtle"
        fontSize="0.65rem"
        textTransform="uppercase"
      >
        Measured
      </Badge>
    </Tooltip>
  );
}

export function SuggestionBadge({ source }: { source?: string }) {
  return (
    <Tooltip
      label={
        source
          ? `Suggestion from ${source}. Review before acting; it never changes grades or records.`
          : 'Suggestion only. Review before acting.'
      }
      hasArrow
    >
      <Badge colorScheme="coral" variant="subtle" fontSize="0.65rem" textTransform="uppercase">
        Suggestion
      </Badge>
    </Tooltip>
  );
}
