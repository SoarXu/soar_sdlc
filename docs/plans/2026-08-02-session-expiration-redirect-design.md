# Session Expiration Redirect Design

## Goal

When a protected API request returns HTTP 401, present a Chinese session-expiration
notice and then redirect the user to the login page.

## Design

The shared Axios client will own the behavior in a response-error interceptor:

1. Detect HTTP 401 responses from protected endpoints.
2. Remove the stored session values used by the auth store.
3. Display `登录状态已失效，请重新登录` once for a burst of concurrent failed requests.
4. Route to `login` automatically after the notice, with the current path in the
   `redirect` query parameter.

Authentication endpoints, including login, are excluded so an invalid login keeps
its existing inline error behavior. The redirect will not be triggered again when
the user is already on the login page.

## Testing

Add focused HTTP-client tests that verify a protected 401 clears session data,
shows the Chinese notice, and routes to login; verify login failures and repeated
401 responses do not create duplicate redirects or notices.
