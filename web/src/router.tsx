// SPDX-License-Identifier: Apache-2.0
import { createBrowserRouter } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Fogon } from './pages/Fogon';
import { Home } from './pages/Home';
import { Mangrullo } from './pages/Mangrullo';
import { NotFound } from './pages/NotFound';
import { Pizarron } from './pages/Pizarron';

export const router = createBrowserRouter([
  // Pizarrón renders without the page shell: transparent overlay for OBS / vMix.
  { path: '/pizarron/:stage', element: <Pizarron /> },
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Home /> },
      { path: 'fogon/:stage', element: <Fogon /> },
      { path: 'mangrullo', element: <Mangrullo /> },
      { path: '*', element: <NotFound /> },
    ],
  },
]);
