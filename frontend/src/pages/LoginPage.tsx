import { useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardBody,
  Container,
  Divider,
  FormControl,
  FormErrorMessage,
  FormLabel,
  Heading,
  Input,
  Stack,
  Text,
  VStack,
} from '@chakra-ui/react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Brand } from '@/components/Brand';
import { ErrorState } from '@/components/StateViews';
import { useLoginMutation } from '@/api/caricueApi';
import { errorMessage, fieldErrors } from '@/api/baseQuery';
import { TAGLINE } from '@/theme';

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [login, { isLoading, error }] = useLoginMutation();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [touched, setTouched] = useState(false);

  const fields = fieldErrors(error);
  const from = (location.state as { from?: string } | null)?.from ?? '/app';

  const emailProblem = touched && !email.trim() ? 'Enter your email address.' : fields.email;
  const passwordProblem = touched && !password ? 'Enter your password.' : fields.password;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (!email.trim() || !password) return;
    try {
      await login({ email: email.trim(), password }).unwrap();
      navigate(from, { replace: true });
    } catch {
      // Rendered from the `error` returned by the mutation hook.
    }
  }

  return (
    <Box minH="100vh" bg="sand.50" py={{ base: 8, md: 16 }}>
      <Container maxW="md">
        <VStack spacing={6} align="stretch">
          <VStack spacing={2}>
            <Brand size="lg" />
            <Text color="cariteal.700" fontWeight="600">
              {TAGLINE}
            </Text>
          </VStack>

          <Card borderWidth="1px" borderColor="sand.200" boxShadow="sm">
            <CardBody>
              <VStack as="form" spacing={4} align="stretch" onSubmit={handleSubmit} noValidate>
                <Heading size="md">Sign in</Heading>

                {error && !Object.keys(fields).length && (
                  <ErrorState title="Could not sign in" message={errorMessage(error)} />
                )}

                <FormControl isInvalid={Boolean(emailProblem)} isRequired>
                  <FormLabel htmlFor="login-email">Email address</FormLabel>
                  <Input
                    id="login-email"
                    name="email"
                    type="email"
                    autoComplete="username"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@school.edu"
                  />
                  <FormErrorMessage>{emailProblem}</FormErrorMessage>
                </FormControl>

                <FormControl isInvalid={Boolean(passwordProblem)} isRequired>
                  <FormLabel htmlFor="login-password">Password</FormLabel>
                  <Input
                    id="login-password"
                    name="password"
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <FormErrorMessage>{passwordProblem}</FormErrorMessage>
                </FormControl>

                <Button type="submit" isLoading={isLoading} loadingText="Signing in…" size="lg">
                  Sign in
                </Button>

                <Divider />
                <Stack spacing={2} fontSize="sm">
                  <Text>
                    New to CariCue?{' '}
                    <Link
                      to="/register"
                      style={{ textDecoration: 'underline', fontWeight: 600 }}
                    >
                      Create a teacher account
                    </Link>
                  </Text>
                  <Text>
                    Are you a student?{' '}
                    <Link to="/join" style={{ textDecoration: 'underline', fontWeight: 600 }}>
                      Join with a session code
                    </Link>
                  </Text>
                </Stack>
              </VStack>
            </CardBody>
          </Card>
        </VStack>
      </Container>
    </Box>
  );
}
