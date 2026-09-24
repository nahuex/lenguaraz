// SPDX-License-Identifier: Apache-2.0
import { Link } from 'react-router-dom';

export function NotFound() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold tracking-tight">Page not found</h1>
      <p className="text-ink-muted">There is nothing at this address.</p>
      <Link to="/" className="w-fit text-accent underline">
        Back to the stage list
      </Link>
    </div>
  );
}
