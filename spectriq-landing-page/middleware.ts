import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server'

// /dashboard and /results require a signed-in Clerk session; the landing
// page and the sign-in/sign-up screens stay public.
const isProtectedRoute = createRouteMatcher(['/dashboard(.*)', '/results(.*)'])

export default clerkMiddleware(async (auth, req) => {
  if (isProtectedRoute(req)) {
    await auth.protect({ unauthenticatedUrl: new URL('/', req.url).toString() })
  }
})

export const config = {
  matcher: [
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    '/(api|trpc)(.*)',
  ],
}
