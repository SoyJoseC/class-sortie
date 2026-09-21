import { useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardBody,
  Divider,
  FormControl,
  FormHelperText,
  FormLabel,
  Heading,
  Input,
  Text,
  useToast,
  VStack,
} from '@chakra-ui/react';
import type { Teacher } from '@/api/types';
import {
  useClientConfigQuery,
  useCurrentTeacherQuery,
  useUpdateProfileMutation,
} from '@/api/caricueApi';
import { errorMessage } from '@/api/baseQuery';
import { ErrorState, LoadingState } from '@/components/StateViews';
import { formatDateTime } from '@/utils/insightFormat';

export function ProfilePage() {
  const { data: teacher, isLoading, isError, error } = useCurrentTeacherQuery();

  if (isLoading) return <LoadingState />;
  if (isError || !teacher) return <ErrorState message={errorMessage(error)} />;

  return <ProfileForm teacher={teacher} />;
}

function ProfileForm({ teacher }: { teacher: Teacher }) {
  const { data: config } = useClientConfigQuery();
  const [update, updateState] = useUpdateProfileMutation();
  const toast = useToast();

  const [fullName, setFullName] = useState(teacher.full_name);
  const [schoolName, setSchoolName] = useState(teacher.school_name);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    try {
      await update({ full_name: fullName.trim(), school_name: schoolName.trim() }).unwrap();
      toast({ title: 'Profile updated', status: 'success', duration: 2500 });
    } catch (updateError) {
      toast({ title: errorMessage(updateError), status: 'error' });
    }
  }

  return (
    <VStack spacing={5} align="stretch" maxW="2xl">
      <Box>
        <Heading size="lg">Your profile</Heading>
        <Text color="gray.600">Joined {formatDateTime(teacher.date_joined)}</Text>
      </Box>

      <Card borderWidth="1px" borderColor="sand.200" as="form" onSubmit={handleSubmit}>
        <CardBody>
          <VStack spacing={4} align="stretch">
            <FormControl>
              <FormLabel htmlFor="profile-email">Email</FormLabel>
              <Input id="profile-email" value={teacher.email} isReadOnly bg="sand.100" />
              <FormHelperText>
                Used to sign in. Contact an administrator to change it.
              </FormHelperText>
            </FormControl>

            <FormControl isRequired>
              <FormLabel htmlFor="profile-name">Full name</FormLabel>
              <Input
                id="profile-name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
              />
            </FormControl>

            <FormControl>
              <FormLabel htmlFor="profile-school">School</FormLabel>
              <Input
                id="profile-school"
                value={schoolName}
                onChange={(e) => setSchoolName(e.target.value)}
              />
            </FormControl>

            <Button
              type="submit"
              variant="accent"
              alignSelf="flex-start"
              isLoading={updateState.isLoading}
              loadingText="Saving…"
            >
              Save changes
            </Button>
          </VStack>
        </CardBody>
      </Card>

      <Card borderWidth="1px" borderColor="sand.200">
        <CardBody>
          <Heading size="sm" mb={3}>
            This deployment
          </Heading>
          <VStack align="stretch" spacing={2} fontSize="sm" color="gray.700">
            <Text>
              Student join links point at <strong>{config?.public_base_url ?? '—'}</strong>.
            </Text>
            <Text>
              Live dashboards refresh every {config?.dashboard_poll_seconds ?? '—'} seconds.
            </Text>
            <Text>
              Activities take {config?.min_questions ?? 1}–{config?.max_questions ?? 5}{' '}
              questions.
            </Text>
            <Divider />
            <Text>
              AI suggestions are{' '}
              <strong>{config?.ai_suggestions_enabled ? 'enabled' : 'disabled'}</strong>. With
              them disabled, suggestions come from the rule-based provider only — no student
              text leaves this server.
            </Text>
          </VStack>
        </CardBody>
      </Card>
    </VStack>
  );
}
