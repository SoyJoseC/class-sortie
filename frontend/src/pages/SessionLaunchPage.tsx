import { useState } from 'react';
import {
  Alert,
  AlertIcon,
  Badge,
  Box,
  Button,
  Card,
  CardBody,
  Code,
  Divider,
  Flex,
  Heading,
  HStack,
  Text,
  useClipboard,
  useToast,
  VStack,
} from '@chakra-ui/react';
import { QRCodeSVG } from 'qrcode.react';
import { Link, useParams } from 'react-router-dom';
import { useCloseSessionMutation, useSessionQuery } from '@/api/caricueApi';
import { errorMessage } from '@/api/baseQuery';
import { ErrorState, LoadingState } from '@/components/StateViews';
import { formatSessionCode } from '@/utils/insightFormat';

/**
 * The screen a teacher projects.
 *
 * The QR code encodes `session.join_url`, which the backend builds from
 * `PUBLIC_BASE_URL` — so the link is correct for however the deployment is
 * reached, not for whatever host the teacher's browser happens to be on.
 */
export function SessionLaunchPage() {
  const { id } = useParams<{ id: string }>();
  const sessionId = Number(id);
  const toast = useToast();

  const { data, isLoading, isError, error, refetch } = useSessionQuery(sessionId, {
    // Keeps the participant counter fresh while the code is on screen.
    pollingInterval: 4000,
  });
  const [closeSession, closeState] = useCloseSessionMutation();
  const [bigCode, setBigCode] = useState(true);

  const { onCopy, hasCopied } = useClipboard(data?.join_url ?? '');

  if (isLoading) return <LoadingState label="Loading session…" />;
  if (isError || !data) {
    return (
      <ErrorState
        message={errorMessage(error, 'Session not found.')}
        onRetry={() => void refetch()}
      />
    );
  }

  async function handleClose() {
    try {
      await closeSession(sessionId).unwrap();
      toast({
        title: 'Session closed',
        description: 'No more submissions will be accepted.',
        status: 'success',
      });
    } catch (closeError) {
      toast({ title: errorMessage(closeError), status: 'error' });
    }
  }

  return (
    <VStack spacing={6} align="stretch">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap={3}>
        <Box>
          <HStack>
            <Heading size="lg">{data.activity_title}</Heading>
            <Badge colorScheme={data.status === 'open' ? 'cariteal' : 'gray'} variant="solid">
              {data.status}
            </Badge>
          </HStack>
          <Text color="gray.600">
            {data.classroom_name}
            {data.activity_topic ? ` · ${data.activity_topic}` : ''}
          </Text>
        </Box>
        <HStack>
          <Button as={Link} to={`/app/sessions/${sessionId}`} variant="outline">
            Live results
          </Button>
          {data.status === 'open' && (
            <Button
              variant="accent"
              onClick={handleClose}
              isLoading={closeState.isLoading}
              loadingText="Closing…"
            >
              Close session
            </Button>
          )}
        </HStack>
      </Flex>

      {data.status === 'closed' && (
        <Alert status="info" borderRadius="md">
          <AlertIcon />
          This session is closed. Students can no longer join or submit.
        </Alert>
      )}

      <Card borderWidth="1px" borderColor="sand.200">
        <CardBody>
          <Flex
            direction={{ base: 'column', md: 'row' }}
            gap={8}
            align="center"
            justify="center"
          >
            <VStack spacing={3}>
              <Text fontWeight="700" color="gray.600" textTransform="uppercase" fontSize="sm">
                Scan to join
              </Text>
              <Box bg="white" p={4} borderWidth="1px" borderColor="sand.200" borderRadius="lg">
                <QRCodeSVG
                  value={data.join_url}
                  size={bigCode ? 260 : 160}
                  level="M"
                  fgColor="#0B3C5D"
                  bgColor="#FFFFFF"
                  title={`QR code to join session ${data.code}`}
                />
              </Box>
              <Button size="xs" variant="ghost" onClick={() => setBigCode((value) => !value)}>
                {bigCode ? 'Smaller code' : 'Bigger code'}
              </Button>
            </VStack>

            <Divider orientation="vertical" h="14rem" display={{ base: 'none', md: 'block' }} />

            <VStack spacing={4} align={{ base: 'center', md: 'flex-start' }}>
              <Box textAlign={{ base: 'center', md: 'left' }}>
                <Text fontWeight="700" color="gray.600" textTransform="uppercase" fontSize="sm">
                  Or enter this code
                </Text>
                <Text
                  fontFamily="mono"
                  fontSize={{ base: '4xl', md: '6xl' }}
                  fontWeight="800"
                  color="ocean.700"
                  letterSpacing="0.1em"
                  lineHeight="1.1"
                >
                  {formatSessionCode(data.code)}
                </Text>
                <Text fontSize="sm" color="gray.600">
                  Students go to <Code>{new URL(data.join_url).origin}/join</Code>
                </Text>
              </Box>

              <HStack>
                <Button onClick={onCopy} variant="outline" size="sm">
                  {hasCopied ? 'Link copied' : 'Copy join link'}
                </Button>
                <Button
                  as="a"
                  href={data.join_url}
                  target="_blank"
                  rel="noopener"
                  size="sm"
                  variant="ghost"
                >
                  Open student view
                </Button>
              </HStack>

              <Box bg="sand.100" px={4} py={3} borderRadius="md" w="full">
                <HStack spacing={6} justify="space-between">
                  <Box>
                    <Text
                      fontSize="xs"
                      color="gray.600"
                      textTransform="uppercase"
                      fontWeight="700"
                    >
                      Joined
                    </Text>
                    <Text fontSize="2xl" fontWeight="800" color="ocean.700">
                      {data.participant_count}
                    </Text>
                  </Box>
                  <Box>
                    <Text
                      fontSize="xs"
                      color="gray.600"
                      textTransform="uppercase"
                      fontWeight="700"
                    >
                      Submitted
                    </Text>
                    <Text fontSize="2xl" fontWeight="800" color="cariteal.700">
                      {data.submitted_count}
                      {data.roster_size > 0 && (
                        <Text as="span" fontSize="md" color="gray.600">
                          {' '}
                          / {data.roster_size}
                        </Text>
                      )}
                    </Text>
                  </Box>
                </HStack>
              </Box>

              <Text fontSize="sm" color="gray.600" maxW="20rem">
                {data.identity_mode === 'roster_identifier'
                  ? 'Students must enter their roster identifier. Your class list is never shown on the public page.'
                  : 'Students type a display name. No accounts, no app to install.'}
              </Text>
            </VStack>
          </Flex>
        </CardBody>
      </Card>
    </VStack>
  );
}
