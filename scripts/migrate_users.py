import uuid
from sqlalchemy import text, inspect
from app.database import engine, SessionLocal

def migrate():
    insp = inspect(engine)
    cols = [c['name'] for c in insp.get_columns('users')]
    acc_cols = [c['name'] for c in insp.get_columns('accounts')]
    db = SessionLocal()
    try:
        if 'owner_id' not in acc_cols:
            print("Adding 'owner_id' column to accounts...")
            db.execute(text("ALTER TABLE accounts ADD COLUMN owner_id INT NULL"))
            db.commit()

        if 'uuid' not in cols:
            print("Adding 'uuid' column...")
            db.execute(text("ALTER TABLE users ADD COLUMN uuid VARCHAR(36) NULL"))
        if 'account_id' not in cols:
            print("Adding 'account_id' column...")
            db.execute(text("ALTER TABLE users ADD COLUMN account_id INT NULL, ADD CONSTRAINT fk_users_account FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE"))
        if 'role' not in cols:
            print("Adding 'role' column...")
            db.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(50) NOT NULL DEFAULT 'admin'"))
        if 'is_active' not in cols:
            print("Adding 'is_active' column...")
            db.execute(text("ALTER TABLE users ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1"))
        if 'updated_at' not in cols:
            print("Adding 'updated_at' column...")
            db.execute(text("ALTER TABLE users ADD COLUMN updated_at DATETIME NULL"))

        # Update existing records
        db.execute(text("UPDATE users SET uuid = UUID() WHERE uuid IS NULL OR uuid = ''"))
        db.execute(text("UPDATE users SET account_id = 1 WHERE account_id IS NULL"))
        db.commit()
        print("Database migration completed successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
