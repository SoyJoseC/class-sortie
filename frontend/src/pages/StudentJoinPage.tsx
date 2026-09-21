import { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardBody,
  FormControl,
  FormErrorMessage,
  FormHelperText,
  FormLabel,
  Heading,
  Input,
  Text,
} from '@chakra-ui/react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useLazyLookupCodeQuery } from '@/api/caricueApi';
import { errorMessage } from '@/api/baseQuery';
import { StudentShell } from '@/components/StudentShell';

const CODE_LENGTH = 6;

/**
 * Where a student lands after typing the short code the teacher projected.
 *
 * The code is only an index into the session; the unguessable public token it
 * resolves to is what the rest of the flow uses, and this lookup is throttled
 * on the server to make code-guessing impractical.
 */
export function StudentJoinPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [code, setCode] = useState((searchParams.get('code') ?? '').toUpperCase());
  const [touched, setTouched] = useState(false);
  const [lookup, { isFetching, error }] = useLazyLookupCodeQuery();

  const normalized = code.replace(/[^A-Z0-9]/gi, '').toUpperCase();
  const isComplete = normalized.length === CODE_LENGTH;

  // Deep link from a QR scan or a shared "?code=" link: submit for them.
  useEffect(() => {
    const initial = (searchParams.get('code') ?? '').replace(/[^A-Z0-9]/gi, '').toUpperCase();
    if (initial.length === CODE_LENGTH) {
      void resolve(initial);
    }
    // Intentionally runs once, on the initial query string only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function resolve(value: string) {
    try {
      const result = await lookup(value).unwrap();
      navigate(`/s/${result.public_token}`);
    } catch {
      // Rendered below.
    }
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (!isComplete) return;
    await resolve(normalized);
  }

  return (
    <StudentShell subtitle="Join your teacher's activity">
      <Card as="form" onSubmit={handleSubmit} borderWidth="1px" borderColor="sand.200">
        <CardBody>
          <Heading size="md" color="ocean.800" mb={1}>
            Enter your code
          </Heading>
          <Text fontSize="sm" color="gray.600" mb={4}>
            Six letters and numbers from the board. You do not need an account.
          </Text>

          <FormControl isInvalid={(touched && !isComplete) || Boolean(error)} isRequired>
            <FormLabel htmlFor="session-code">Session code</FormLabel>
            <Input
              id="session-code"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              onBlur={() => setTouched(true)}
              placeholder="ABC123"
              autoComplete="off"
              autoCapitalize="characters"
              autoCorrect="off"
              spellCheck={false}
              inputMode="text"
              maxLength={8}
              size="lg"
              fontFamily="mono"
              fontSize="2xl"
              letterSpacing="0.2em"
              textAlign="center"
              enterKeyHint="go"
            />
            <FormErrorMessage>
              {error
                ? errorMessage(error, 'No open activity with that code.')
                : 'Six characters.'}
            </FormErrorMessage>
            {!error && isComplete && <FormHelperText>Looks right — tap Join.</FormHelperText>}
          </FormControl>

          <Button
            type="submit"
            variant="accent"
            size="lg"
            w="full"
            mt={5}
            isLoading={isFetching}
            loadingText="Finding activity…"
            isDisabled={!isComplete}
          >
            Join
          </Button>
        </CardBody>
      </Card>

      <Box>
        <Text fontSize="sm" color="gray.700">
          Scanning the QR code takes you straight in. If the code does not work, the teacher may
          have closed the activity.
        </Text>
      </Box>
    </StudentShell>
  );
}
