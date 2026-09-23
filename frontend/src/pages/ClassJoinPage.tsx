import { useEffect, useState } from 'react';
import {
  Alert,
  AlertIcon,
  Box,
  Button,
  Card,
  CardBody,
  FormControl,
  FormLabel,
  Heading,
  Text,
  VStack,
} from '@chakra-ui/react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import {
  useJoinClassMutation,
  usePublicClassQuery,
  useStudentMeQuery,
} from '@/api/caricueApi';
import { errorMessage } from '@/api/baseQuery';
import { ErrorState, LoadingState } from '@/components/StateViews';
import { StudentShell } from '@/components/StudentShell';
import { googleLoginUrl, oauthErrorMessage } from '@/utils/googleAuth';

type Phase = 'join' | 'done';

export function ClassJoinPage() {
  const { inviteToken = '' } = useParams<{ inviteToken: string }>();
  const [searchParams] = useSearchParams();
  const oauthError = oauthErrorMessage(searchParams.get('oauth_error'));

  const classInfo = usePublicClassQuery(inviteToken);
  const studentMe = useStudentMeQuery();
  const [joinClass, joinState] = useJoinClassMutation();

  const [phase, setPhase] = useState<Phase>('join');
  const [classroomName, setClassroomName] = useState('');
  const [alreadyEnrolled, setAlreadyEnrolled] = useState(false);

  useEffect(() => {
    if (phase !== 'join' || !studentMe.data || joinState.isLoading || joinState.isSuccess) {
      return;
    }
    void joinClass(inviteToken)
      .unwrap()
      .then((result) => {
        setClassroomName(result.classroom_name);
        setAlreadyEnrolled(result.already_enrolled);
        setPhase('done');
      })
      .catch(() => {
        // Shown inline below.
      });
  }, [inviteToken, joinClass, joinState.isLoading, joinState.isSuccess, phase, studentMe.data]);

  if (classInfo.isLoading) return <LoadingState label="Loading class…" />;
  if (classInfo.isError || !classInfo.data) {
    return (
      <StudentShell>
        <ErrorState
          title="Class not found"
          message={errorMessage(
            classInfo.error,
            'This class link is not valid. Ask your teacher for a new QR code.'
          )}
        />
        <Button as={Link} to="/join" variant="outline">
          Join a live activity instead
        </Button>
      </StudentShell>
    );
  }

  const info = classInfo.data;

  if (phase === 'done') {
    return (
      <StudentShell subtitle={classroomName}>
        <Alert status="success" borderRadius="md">
          <AlertIcon />
          <Box>
            <Text fontWeight="700">
              {alreadyEnrolled ? "You're already in this class." : 'You joined this class.'}
            </Text>
            <Text fontSize="sm" mt={1}>
              When your teacher launches an activity, join with the session code as usual.
            </Text>
          </Box>
        </Alert>
        <Button as={Link} to="/join" variant="accent" w="full">
          Enter a session code
        </Button>
      </StudentShell>
    );
  }

  if (!info.self_enrollment_enabled) {
    return (
      <StudentShell subtitle={info.name}>
        <Alert status="warning" borderRadius="md">
          <AlertIcon />
          <Text fontSize="sm">
            This class is not accepting self-enrollment. Ask your teacher to add you to the roster.
          </Text>
        </Alert>
      </StudentShell>
    );
  }

  const signedIn = Boolean(studentMe.data);
  const nextUrl = `/join/class/${inviteToken}`;

  return (
    <StudentShell subtitle={info.name} googleAccountMode>
      <Box>
        <Heading size="md" color="ocean.800">
          Join {info.name}
        </Heading>
        {info.subject && (
          <Text fontSize="sm" color="cariteal.700">
            {info.subject}
            {info.level ? ` · ${info.level}` : ''}
          </Text>
        )}
        <Text fontSize="sm" color="gray.600" mt={1}>
          Teacher: {info.teacher_name}
        </Text>
      </Box>

      {oauthError && (
        <Alert status="error" borderRadius="md">
          <AlertIcon />
          <Text fontSize="sm">{oauthError}</Text>
        </Alert>
      )}

      {joinState.error && (
        <ErrorState
          title="Could not join"
          message={errorMessage(joinState.error, 'Please try again or ask your teacher.')}
        />
      )}

      <Card borderWidth="1px" borderColor="sand.200">
        <CardBody>
          {signedIn ? (
            <VStack align="stretch" spacing={4}>
              <FormControl>
                <FormLabel>Signed in as</FormLabel>
                <Text fontWeight="600">{studentMe.data!.full_name}</Text>
                <Text fontSize="sm" color="gray.600">
                  {studentMe.data!.email}
                </Text>
              </FormControl>
              <Button
                variant="accent"
                size="lg"
                w="full"
                isLoading={joinState.isLoading}
                loadingText="Joining…"
                onClick={() =>
                  void joinClass(inviteToken)
                    .unwrap()
                    .then((result) => {
                      setClassroomName(result.classroom_name);
                      setAlreadyEnrolled(result.already_enrolled);
                      setPhase('done');
                    })
                }
              >
                Join class
              </Button>
            </VStack>
          ) : (
            <VStack align="stretch" spacing={4}>
              <Text fontSize="sm" color="gray.600">
                Sign in with your school Google account to join this class. Your name and email
                come from Google — nothing to type.
              </Text>
              <Button
                as="a"
                href={googleLoginUrl('student', nextUrl)}
                variant="accent"
                size="lg"
                w="full"
              >
                Sign in with Google
              </Button>
            </VStack>
          )}
        </CardBody>
      </Card>
    </StudentShell>
  );
}
