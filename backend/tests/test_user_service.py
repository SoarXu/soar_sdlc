import unittest

from sqlalchemy import text

from app.core.security import verify_password
from app.db.session import SessionLocal
from app.services.user_service import get_or_create_demo_user


class UserServiceTestCase(unittest.TestCase):
    def test_admin_user_uses_password_hash_column(self):
        db = SessionLocal()
        try:
            existing_admin = db.execute(text("select id from users where username = 'admin'")).first()
            user = get_or_create_demo_user(db)

            self.assertEqual(user.username, "admin")
            self.assertTrue(verify_password("admin123", user.password_hash))
            stale_users = db.execute(
                text("select username from users where username in ('pm_chen', 'rd_lin', 'qa_wang', 'po_li')")
            ).all()
            self.assertEqual(stale_users, [])
        finally:
            if not existing_admin:
                db.execute(text("delete from user_roles where user_id in (select id from users where username = 'admin')"))
                db.execute(text("delete from users where username = 'admin'"))
                db.commit()
            db.close()


if __name__ == "__main__":
    unittest.main()
