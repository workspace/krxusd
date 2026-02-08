import { NextRequest, NextResponse } from 'next/server';

export function middleware(request: NextRequest) {
  const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';
  const url = new URL(request.url);
  const target = `${backendUrl}${url.pathname}${url.search}`;

  return NextResponse.rewrite(new URL(target));
}

export const config = {
  matcher: '/api/:path*',
};
