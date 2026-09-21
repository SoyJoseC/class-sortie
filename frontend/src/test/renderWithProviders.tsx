import { ChakraProvider } from '@chakra-ui/react';
import { configureStore } from '@reduxjs/toolkit';
import { render } from '@testing-library/react';
import { Provider } from 'react-redux';
import { MemoryRouter } from 'react-router-dom';
import type { ReactElement, ReactNode } from 'react';
import { caricueApi } from '@/api/caricueApi';
import { theme } from '@/theme';

/**
 * Renders a component with everything the app provides at runtime.
 *
 * A fresh store per test keeps RTK Query's cache from leaking between cases.
 */
export function renderWithProviders(
  ui: ReactElement,
  { route = '/' }: { route?: string } = {}
) {
  const store = configureStore({
    reducer: { [caricueApi.reducerPath]: caricueApi.reducer },
    middleware: (getDefault) => getDefault().concat(caricueApi.middleware),
  });

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <Provider store={store}>
        <ChakraProvider theme={theme}>
          <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
        </ChakraProvider>
      </Provider>
    );
  }

  return { store, ...render(ui, { wrapper: Wrapper }) };
}
