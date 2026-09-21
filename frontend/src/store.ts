import { configureStore } from '@reduxjs/toolkit';
import { setupListeners } from '@reduxjs/toolkit/query';
import { caricueApi } from './api/caricueApi';

export function createStore() {
  const store = configureStore({
    reducer: { [caricueApi.reducerPath]: caricueApi.reducer },
    middleware: (getDefault) => getDefault().concat(caricueApi.middleware),
  });
  // Refetch when the tab regains focus or the network comes back, which
  // matters on the live dashboard and on a student's phone.
  setupListeners(store.dispatch);
  return store;
}

export const store = createStore();

export type AppStore = ReturnType<typeof createStore>;
export type RootState = ReturnType<AppStore['getState']>;
export type AppDispatch = AppStore['dispatch'];
