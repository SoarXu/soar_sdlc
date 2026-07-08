# System Admin User And Role Management Design

## Goal

Only users with the `system_admin` role can maintain roles and users. Administrators can create users with a secure one-time initial password. Users created this way must change the password on first login before using the system.

## Backend Design

- Add an authenticated admin dependency that resolves the Bearer token to the current active user and requires an enabled `system_admin` role.
- Protect role mutation APIs:
  - `POST /api/v1/roles`
  - `PUT /api/v1/roles/{role_id}`
  - `DELETE /api/v1/roles/{role_id}`
- Protect user administration APIs:
  - `POST /api/v1/users`
  - `PUT /api/v1/users/{user_id}/roles`
  - `POST /api/v1/users/{user_id}/reset-password`
- Keep read APIs usable by authenticated application users where existing screens depend on user and role lookup data.

## Password Flow

- Add `users.must_change_password`, defaulting to `false` for seeded/admin users.
- Admin-created users are saved with `must_change_password=true`.
- Initial passwords are generated with a cryptographically secure random generator and include uppercase, lowercase, digits, and symbols.
- Plain initial passwords are never stored. They are returned once in the create/reset response as `initial_password`.
- Resetting a user password generates a new one-time password and sets `must_change_password=true`.
- `POST /api/v1/auth/change-password` requires the current password and a new password. On success it updates the password hash and clears `must_change_password`.

## Login Flow

- `POST /api/v1/auth/login` returns `must_change_password`.
- The frontend stores this flag with the session.
- If the flag is true, the user is routed to a forced password-change screen and cannot continue into the main app until the password is changed.

## Frontend Design

- Role Management gains:
  - `新增用户` action for system administrators.
  - A create-user dialog with username, full name, email, mobile, department, and role selection.
  - A reset-password action per user.
  - A one-time password dialog with copy support after create/reset.
- Existing role creation/edit/delete and user role assignment controls are hidden or disabled for non-admin users. Backend remains the authority.
- Login flow redirects users with `must_change_password=true` to a password-change screen.

## Testing

- Backend tests cover:
  - Non-admin cannot create/update/delete roles.
  - System admin can create roles.
  - System admin can create users and receives a one-time password.
  - Created users must change password after login.
  - Password change clears the flag.
  - Reset password sets the flag again and returns a new one-time password.
- Frontend build verifies the new UI compiles.
