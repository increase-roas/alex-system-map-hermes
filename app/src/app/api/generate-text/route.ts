import { NextResponse } from 'next/server';

export async function POST() {
  return NextResponse.json(
    {
      disabled: true,
      reason:
        'Sample AI provider routes are disabled for the local system map. No OpenAI key is required.',
    },
    { status: 503 },
  );
}
