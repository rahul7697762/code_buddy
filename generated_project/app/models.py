"""SQLAlchemy ORM models for the blog application.

This module defines the database schema using SQLAlchemy's declarative
base. The `BlogPost` model represents a blog post with a title, content,
and timestamp.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func

# Import the declarative base from the database module.
from app.database import Base


class BlogPost(Base):
    """Model representing a blog post.

    Attributes
    ----------
    id: int
        Primary key, auto‑incremented.
    title: str
        Title of the blog post, limited to 200 characters.
    content: str
        Full text content of the post.
    created_at: datetime
        Timestamp of when the post was created. Defaults to the current
        time on the database server.
    """

    __tablename__ = "blog_posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
