// SPDX-License-Identifier: Apache-2.0
import { createBrowserRouter } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Fogon } from './pages/Fogon';
import { Home } from './pages/Home';
import { NotFound } from './pages/NotFound';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Home /> },
      { path: 'fogon/:stage', element: <Fogon /> },
      { path: '*', element: <NotFound /> },
    ],
  },
]);
