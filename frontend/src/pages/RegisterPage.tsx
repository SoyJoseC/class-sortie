import { useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardBody,
  Container,
  FormControl,
  FormErrorMessage,
  FormHelperText,
  FormLabel,
  Heading,
  Input,
  Text,
  VStack,
} from '@chakra-ui/react';
import { Link, useNavigate } from 'react-router-dom';
import { Brand } from '@/components/Brand';
import { ErrorState } from '@/components/StateViews';
import { useRegisterMutation } from '@/api/caricueApi';
import { errorMessage, fieldErrors } from '@/api/baseQuery';

const MIN_PASSWORD_LENGTH = 10;

export function RegisterPage() {
  const navigate = useNavigate();
  const [register, { isLoading, error }] = useRegisterMutation();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [schoolName, setSchoolName] = useState('');
  const [password, setPassword] = useState('');
  const [touched, setTouched] = useState(false);

  const fields = fieldErrors(error);

  const nameProblem =
    touched && fullName.trim().length < 2 ? 'Enter your name.' : fields.full_name;
  const emailProblem = touched && !email.trim() ? 'Enter your email address.' : fields.email;
  const passwordProblem =
    touched && password.length < MIN_PASSWORD_LENGTH
      ? `Use at least ${MIN_PASSWORD_LENGTH} characters.`
      : fields.password;

  const isFormFillable =
    fullName.trim().length >= 2 &&
    email.trim().length > 0 &&
    password.length >= MIN_PASSWORD_LENGTH;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (!isFormFillable) return;
    try {
      await register({
        full_name: fullName.trim(),
        email: email.trim(),
        school_name: schoolName.trim(),
        password,
      }).unwrap();
      // Registration signs the teacher in, so go straight to the dashboard.
      navigate('/app', { replace: true });
    } catch {
      // Rendered from the mutation's `error`.
    }
  }

  return (
    <Box minH="100vh" bg="sand.50" py={{ base: 8, md: 16 }}>
      <Container maxW="md">
        <VStack spacing={6} align="stretch">
          <Brand size="lg" showTagline />

          <Card borderWidth="1px" borderColor="sand.200" boxShadow="sm">
            <CardBody>
              <VStack as="form" spacing={4} align="stretch" onSubmit={handleSubmit} noValidate>
                <Heading size="md">Create a teacher account</Heading>
                <Text fontSize="sm" color="gray.600">
                  Only teachers need an account. Your students join a session with a code — they
                  never sign up.
                </Text>

                {error && !Object.keys(fields).length && (
                  <ErrorState
                    title="Could not create your account"
                    message={errorMessage(error)}
                  />
                )}

                <FormControl isInvalid={Boolean(nameProblem)} isRequired>
                  <FormLabel htmlFor="register-name">Your name</FormLabel>
                  <Input
                    id="register-name"
                    name="full_name"
                    autoComplete="name"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                  />
                  <FormErrorMessage>{nameProblem}</FormErrorMessage>
                </FormControl>

                <FormControl isInvalid={Boolean(emailProblem)} isRequired>
                  <FormLabel htmlFor="register-email">Email address</FormLabel>
                  <Input
                    id="register-email"
                    name="email"
                    type="email"
                    autoComplete="username"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                  <FormErrorMessage>{emailProblem}</FormErrorMessage>
                </FormControl>

                <FormControl isInvalid={Boolean(fields.school_name)}>
                  <FormLabel htmlFor="register-school">School (optional)</FormLabel>
                  <Input
                    id="register-school"
                    name="school_name"
                    value={schoolName}
                    onChange={(e) => setSchoolName(e.target.value)}
                  />
                  <FormErrorMessage>{fields.school_name}</FormErrorMessage>
                </FormControl>

                <FormControl isInvalid={Boolean(passwordProblem)} isRequired>
                  <FormLabel htmlFor="register-password">Password</FormLabel>
                  <Input
                    id="register-password"
                    name="password"
                    type="password"
                    autoComplete="new-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  {passwordProblem ? (
                    <FormErrorMessage>{passwordProblem}</FormErrorMessage>
                  ) : (
                    <FormHelperText>
                      At least {MIN_PASSWORD_LENGTH} characters. Avoid common passwords.
                    </FormHelperText>
                  )}
                </FormControl>

                <Button
                  type="submit"
                  isLoading={isLoading}
                  loadingText="Creating account…"
                  size="lg"
                >
                  Create account
                </Button>

                <Text fontSize="sm">
                  Already have an account?{' '}
                  <Link to="/login" style={{ textDecoration: 'underline', fontWeight: 600 }}>
                    Sign in
                  </Link>
                </Text>
              </VStack>
            </CardBody>
          </Card>
        </VStack>
      </Container>
    </Box>
  );
}
