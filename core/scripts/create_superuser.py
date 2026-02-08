import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import User
from core.auth import hash_password

async def create_or_upgrade_superuser():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == "admin@example.com"))
        user = result.scalars().first()

        if user:
            if not user.is_superuser:
                user.is_superuser = True
                user.is_staff = True
                if not user.hashed_password:
                    user.hashed_password = hash_password("admin123")
                await session.commit()
                print("🔼 Existing user upgraded to superuser: admin@example.com")
            else:
                print("⚠️ Superuser already exists, skipping.")
        else:
            default_superuser = User(
                email="admin@example.com",
                hashed_password=hash_password("admin123"),
                is_superuser=True,
                is_staff=True,
            )
            session.add(default_superuser)
            await session.commit()
            print("✅ New superuser created: admin@example.com / admin123")

if __name__ == "__main__":
    asyncio.run(create_or_upgrade_superuser())
