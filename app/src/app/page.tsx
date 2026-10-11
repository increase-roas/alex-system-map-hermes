import Link from 'next/link';

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-lg font-medium">Alex system map</h1>
      <p className="text-muted-foreground max-w-md text-center text-sm">
        Local foundation viewer and workflow tracker. Sample AI workflow routes are disabled.
      </p>
      <Link className="underline" href="/explorer">
        Open explorer
      </Link>
    </main>
  );
}
