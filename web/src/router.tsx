// SPDX-License-Identifier: Apache-2.0
import { createBrowserRouter } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Admin } from './pages/Admin';
import { Home } from './pages/Home';
import { LiveCaptions } from './pages/LiveCaptions';
import { NotFound } from './pages/NotFound';
import { Overlay } from './pages/Overlay';

export const router = createBrowserRouter([
  // The overlay renders without the page shell: transparent browser source for OBS / vMix.
  { path: '/overlay/:stage', element: <Overlay /> },
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Home /> },
      { path: 'live/:stage', element: <LiveCaptions /> },
      { path: 'admin', element: <Admin /> },
      { path: '*', element: <NotFound /> },
    ],
  },
]);
