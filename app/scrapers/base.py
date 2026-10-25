from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ScrapedPost:
    post_id: str
    subreddit: str
    title: str
    body: str
    author: str
    author_karma: int
    score: int
    num_comments: int
    url: str
    posted_at: datetime


class RedditSource(ABC):
    """Abstract interface for a Reddit data source.
    Swap out the implementation to switch providers (Apify, Bright Data, etc.)."""

    @abstractmethod
    async def fetch_new(self, subreddits: list[str], max_items: int = 50) -> list[ScrapedPost]:
        ...
