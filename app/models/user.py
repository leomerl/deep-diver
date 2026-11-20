from datetime import UTC, datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class UserBase(SQLModel):
    github_id: int = Field(unique=True)  # GitHub's stable id; the login can be renamed
    login: str = Field(max_length=64)


class User(UserBase, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    # Fernet ciphertext of the OAuth token, never the token itself: it reads the user's private repos.
    access_token_enc: str = Field(max_length=512)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), sa_type=sa.DateTime(timezone=True))


class UserRead(UserBase):
    id: int
