// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';

/**
 * Smoke test for the copied shadcn/ui primitives: they resolve through the `@` alias,
 * render in jsdom and expose the ARIA roles the pages and the axe checks rely on.
 */
describe('shadcn/ui primitives', () => {
  it('render with accessible roles and names', () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Stage</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert>
            <AlertTitle>Status</AlertTitle>
            <AlertDescription>Connected</AlertDescription>
          </Alert>
          <Badge>Live</Badge>
          <Button>Start</Button>
          <Label htmlFor="token">Admin token</Label>
          <Input id="token" />
          <RadioGroup aria-label="Language" defaultValue="es">
            <RadioGroupItem value="en" aria-label="English" />
            <RadioGroupItem value="es" aria-label="Spanish" />
          </RadioGroup>
          <ToggleGroup type="single" aria-label="Font size" defaultValue="M">
            <ToggleGroupItem value="S">Small</ToggleGroupItem>
            <ToggleGroupItem value="M">Medium</ToggleGroupItem>
          </ToggleGroup>
          <Switch aria-label="Dark mode" defaultChecked />
          <Separator decorative={false} />
          <Skeleton data-testid="skeleton" />
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Stage</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell>main</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>,
    );

    expect(screen.getByRole('alert')).toHaveTextContent('Connected');
    expect(screen.getByRole('button', { name: 'Start' })).toBeInTheDocument();
    expect(screen.getByLabelText('Admin token')).toBeInstanceOf(HTMLInputElement);
    expect(screen.getByRole('radiogroup', { name: 'Language' })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: 'Spanish' })).toHaveAttribute('aria-checked', 'true');
    // Radix ToggleGroup in single mode is a radiogroup whose items are radios.
    expect(screen.getByRole('radiogroup', { name: 'Font size' })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: 'Medium' })).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByRole('switch', { name: 'Dark mode' })).toHaveAttribute(
      'aria-checked',
      'true',
    );
    expect(screen.getByRole('separator')).toBeInTheDocument();
    expect(screen.getByTestId('skeleton')).toBeInTheDocument();
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Stage' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'main' })).toBeInTheDocument();
    expect(screen.getByText('Live')).toBeInTheDocument();
  });
});
