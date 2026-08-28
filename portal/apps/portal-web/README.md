# Private portal web client

This is a noindex, no-store browser shell for the authenticated API. It stores no
session token, household scope, document body, or TOTP secret in localStorage.
Only non-secret interrupted-upload IDs use `sessionStorage`; every resume and
part action is reauthorized by the server and a fresh short-lived capability.

The public marketing snapshot lives separately in `../public-site/`. Do not merge
these directories or deploy portal API routes on the static marketing origin
without the reverse-proxy controls in `deploy/nginx/portal.conf`.
