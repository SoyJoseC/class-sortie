import { extendTheme, type ThemeConfig } from '@chakra-ui/react';

/**
 * CariCue visual identity.
 *
 * Restrained Caribbean cues rather than stereotypes: the deep ocean blue and
 * teal come from water, the coral accent is used sparingly for action and
 * attention, and the background is a warm sand neutral. No flags, no palms.
 *
 * Contrast: `ocean.700` and `teal.700` on `sand.50` and white both exceed the
 * WCAG AA 4.5:1 ratio for body text, and `coral.600` is only used for text on
 * light surfaces (never light-on-coral below 18px).
 */

const config: ThemeConfig = {
  initialColorMode: 'light',
  useSystemColorMode: false,
};

const colors = {
  ocean: {
    50: '#E7EEF3',
    100: '#C2D4E1',
    200: '#9BB8CD',
    300: '#729BB8',
    400: '#4E82A6',
    500: '#2A6A94',
    600: '#17547A',
    700: '#0B3C5D', // primary brand
    800: '#072B43',
    900: '#04192A',
  },
  cariteal: {
    50: '#E4F5F4',
    100: '#BCE7E4',
    200: '#8FD7D2',
    300: '#5FC5BF',
    400: '#36B5AE',
    500: '#17A398',
    600: '#12867E', // AA on white
    700: '#0E6A63',
    800: '#094D48',
    900: '#05302D',
  },
  coral: {
    50: '#FDEDE8',
    100: '#FAD2C6',
    200: '#F6B4A1',
    300: '#F1957B',
    400: '#EC7B5E',
    500: '#E26244',
    600: '#C24A2F', // AA on white for text
    700: '#983A22',
    800: '#6E2917',
    900: '#45180D',
  },
  sand: {
    50: '#FBF9F5',
    100: '#F4F0E8',
    200: '#E8E1D3',
    300: '#D8CEBB',
    400: '#C4B79E',
    500: '#AA9A7D',
  },
};

export const theme = extendTheme({
  config,
  colors,
  fonts: {
    heading:
      "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    body: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
  },
  fontSizes: {
    // Students answer on phones: 16px minimum prevents iOS zoom-on-focus.
    md: '1rem',
  },
  radii: {
    md: '0.5rem',
    lg: '0.75rem',
  },
  styles: {
    global: {
      'html, body': {
        backgroundColor: 'sand.50',
        color: 'ocean.900',
        fontSize: '16px',
      },
      '*:focus-visible': {
        outline: '3px solid',
        outlineColor: 'cariteal.600',
        outlineOffset: '2px',
      },
    },
  },
  components: {
    Button: {
      baseStyle: { fontWeight: 600, borderRadius: 'md' },
      defaultProps: { colorScheme: 'ocean' },
      variants: {
        solid: {
          bg: 'ocean.700',
          color: 'white',
          _hover: { bg: 'ocean.800', _disabled: { bg: 'ocean.700' } },
          _active: { bg: 'ocean.900' },
        },
        accent: {
          bg: 'coral.600',
          color: 'white',
          _hover: { bg: 'coral.700' },
          _active: { bg: 'coral.800' },
        },
        outline: {
          borderColor: 'ocean.700',
          color: 'ocean.700',
          _hover: { bg: 'ocean.50' },
        },
      },
    },
    Heading: {
      baseStyle: { color: 'ocean.800', letterSpacing: '-0.01em' },
    },
    Link: {
      baseStyle: {
        color: 'ocean.700',
        textDecoration: 'underline',
        _hover: { color: 'ocean.800' },
      },
    },
  },
});

/** @deprecated Import APP_TAGLINE from `@/branding` in UI code. */
export { APP_TAGLINE as TAGLINE } from '@/branding';
