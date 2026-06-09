import unittest

from app.core.security import verify_password
from app.db.session import SessionLocal
from app.services.user_service import get_or_create_demo_user


class UserServiceTestCase(unittest.TestCase):
    def test_admin_user_uses_password_hash_column(self):
        db = SessionLocal()
        try:
            user = get_or_create_demo_user(db)

            self.assertEqual(user.username, "admin")
            self.assertTrue(verify_password("admin123", user.password_hash))
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
