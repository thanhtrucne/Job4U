"""Assign an existing registered account to admin or a demo partner company."""
import argparse
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from backend.database import AsyncSessionLocal
from backend.models import Company, User


async def assign(email: str, role: str, company_name: str | None) -> None:
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email.lower()))).scalar_one_or_none()
        if user is None:
            raise ValueError("Tài khoản chưa tồn tại. Hãy đăng ký trước.")
        if role == "partner":
            if not company_name:
                raise ValueError("Role partner cần tên công ty đối tác.")
            company = (await db.execute(select(Company).where(Company.name == company_name, Company.is_partner.is_(True)))).scalar_one_or_none()
            if company is None:
                raise ValueError("Không tìm thấy công ty đối tác đã được migration tạo.")
            user.company_id = company.id
        else:
            user.company_id = None
        user.role = role
        await db.commit()
        print(f"Assigned {email} as {role}.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("email")
    parser.add_argument("role", choices=["admin", "partner", "user"])
    parser.add_argument("company_name", nargs="?")
    args = parser.parse_args()
    try:
        asyncio.run(assign(args.email, args.role, args.company_name))
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
