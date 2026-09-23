import {
  Box,
  Button,
  Container,
  Flex,
  HStack,
  Link as ChakraLink,
  Menu,
  MenuButton,
  MenuDivider,
  MenuItem,
  MenuList,
  Text,
} from '@chakra-ui/react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { Brand } from './Brand';
import { useCurrentTeacherQuery, useLogoutMutation } from '@/api/caricueApi';
import { APP_NAME, APP_TAGLINE } from '@/branding';

const NAV_ITEMS = [
  { to: '/app', label: 'Dashboard', end: true },
  { to: '/app/classes', label: 'Classes', end: false },
  { to: '/app/activities', label: 'Activities', end: false },
  { to: '/app/sessions', label: 'Sessions', end: false },
];

export function TeacherLayout() {
  const { data: teacher } = useCurrentTeacherQuery();
  const [logout, { isLoading: isLoggingOut }] = useLogoutMutation();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout()
      .unwrap()
      .catch(() => undefined);
    navigate('/login', { replace: true });
  }

  return (
    <Flex direction="column" minH="100vh">
      <ChakraLink
        href="#main"
        position="absolute"
        left="-9999px"
        _focus={{ left: 2, top: 2, zIndex: 10, bg: 'white', p: 2, borderRadius: 'md' }}
      >
        Skip to main content
      </ChakraLink>

      <Box as="header" bg="white" borderBottomWidth="1px" borderColor="sand.200">
        <Container maxW="7xl" py={3}>
          <Flex align="center" justify="space-between" gap={4} wrap="wrap">
            <Link to="/app" aria-label={`${APP_NAME} dashboard`}>
              <Brand showTagline />
            </Link>

            <HStack as="nav" spacing={1} aria-label="Main navigation">
              {NAV_ITEMS.map((item) => (
                <Button
                  key={item.to}
                  as={NavLink}
                  to={item.to}
                  end={item.end}
                  size="sm"
                  variant="ghost"
                  color="ocean.700"
                  _activeLink={{ bg: 'ocean.50', color: 'ocean.800', fontWeight: 700 }}
                >
                  {item.label}
                </Button>
              ))}
            </HStack>

            <Menu>
              <MenuButton
                as={Button}
                size="sm"
                variant="outline"
                aria-label="Account menu"
                maxW="14rem"
                overflow="hidden"
              >
                <Text noOfLines={1}>{teacher?.full_name ?? 'Account'}</Text>
              </MenuButton>
              <MenuList>
                <Box px={3} py={2}>
                  <Text fontSize="sm" fontWeight="700" color="ocean.800">
                    {teacher?.full_name}
                  </Text>
                  <Text fontSize="xs" color="gray.600">
                    {teacher?.email}
                  </Text>
                </Box>
                <MenuDivider />
                <MenuItem as={Link} to="/app/profile">
                  Profile
                </MenuItem>
                <MenuItem onClick={handleLogout} isDisabled={isLoggingOut}>
                  {isLoggingOut ? 'Signing out…' : 'Sign out'}
                </MenuItem>
              </MenuList>
            </Menu>
          </Flex>
        </Container>
      </Box>

      <Box as="main" id="main" flex="1" py={6}>
        <Container maxW="7xl">
          <Outlet />
        </Container>
      </Box>

      <Box as="footer" borderTopWidth="1px" borderColor="sand.200" py={4}>
        <Container maxW="7xl">
          <Text fontSize="xs" color="gray.600">
            {APP_NAME} · {APP_TAGLINE} · Formative assessment, not a gradebook.
          </Text>
        </Container>
      </Box>
    </Flex>
  );
}
