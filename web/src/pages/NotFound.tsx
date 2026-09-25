// SPDX-License-Identifier: Apache-2.0
import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, SearchX } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';

export function NotFound() {
  useEffect(() => {
    document.title = 'Page not found · Lenguaraz';
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold tracking-tight">Page not found</h1>
      <Alert>
        <SearchX aria-hidden="true" />
        <AlertTitle>There is nothing at this address.</AlertTitle>
        <AlertDescription>
          Check the link you followed, or pick a stage from the list.
        </AlertDescription>
      </Alert>
      <Button asChild className="w-fit">
        <Link to="/">
          <ArrowLeft aria-hidden="true" />
          Back to stages
        </Link>
      </Button>
    </div>
  );
}
