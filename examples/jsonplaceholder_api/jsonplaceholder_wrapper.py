from __future__ import annotations

from typing import Annotated

from pypercache.api_wrapper import ApiWrapper
from pypercache.models.apimodel import Alias, apimodel


BASE_URL = "https://jsonplaceholder.typicode.com"
DEFAULT_CACHE_PATH = "jsonplaceholder_cache.json"
DEFAULT_TIMEOUT = 10
DEFAULT_EXPIRY_SECONDS = 300


@apimodel(validate=True)
class Geo:
    lat: str
    lng: str


@apimodel(validate=True)
class Address:
    street: str
    suite: str
    city: str
    zipcode: str
    geo: Geo


@apimodel(validate=True)
class Company:
    name: str
    catch_phrase: Annotated[str, Alias("catchPhrase")]
    bs: str


@apimodel(validate=True)
class User:
    id: int
    name: str
    username: str
    email: str
    address: Address
    phone: str
    website: str
    company: Company


@apimodel(validate=True)
class Post:
    user_id: Annotated[int, Alias("userId")]
    id: int
    title: str
    body: str


@apimodel(validate=True)
class Comment:
    post_id: Annotated[int, Alias("postId")]
    id: int
    name: str
    email: str
    body: str


@apimodel(validate=True)
class Todo:
    user_id: Annotated[int, Alias("userId")]
    id: int
    title: str
    completed: bool


@apimodel(validate=True)
class CreatedPost:
    user_id: Annotated[int, Alias("userId")]
    id: int
    title: str
    body: str


class JSONPlaceholderClient(ApiWrapper):
    """Small JSONPlaceholder client used as a low-complexity ApiWrapper example."""

    def __init__(
        self,
        *,
        cache_path: str | None = DEFAULT_CACHE_PATH,
        default_expiry: int | float = DEFAULT_EXPIRY_SECONDS,
        request_log_path: str | None = None,
        timeout: int | float | None = DEFAULT_TIMEOUT,
        session=None,
    ) -> None:
        super().__init__(
            origins={"default": BASE_URL},
            default_origin="default",
            cache_path=cache_path,
            default_expiry=default_expiry,
            request_log_path=request_log_path,
            timeout=timeout,
            session=session,
        )

    def get_session(self):
        session = super().get_session()
        session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "pypercache-jsonplaceholder-example/0.1",
            }
        )
        return session

    def list_posts(self) -> list[Post]:
        return self.request("GET", "/posts", expected="json", cast=list[Post])

    def get_post(self, post_id: int) -> Post:
        return self.request("GET", f"/posts/{post_id}", expected="json", cast=Post)

    def get_user(self, user_id: int) -> User:
        return self.request("GET", f"/users/{user_id}", expected="json", cast=User)

    def get_todo(self, todo_id: int) -> Todo:
        return self.request("GET", f"/todos/{todo_id}", expected="json", cast=Todo)

    def list_post_comments(self, post_id: int) -> list[Comment]:
        return self.request(
            "GET",
            f"/posts/{post_id}/comments",
            expected="json",
            cast=list[Comment],
        )

    def create_post(self, *, user_id: int, title: str, body: str) -> CreatedPost:
        return self.request(
            "POST",
            "/posts",
            expected="json",
            json_body={
                "userId": user_id,
                "title": title,
                "body": body,
            },
            use_cache=False,
            cast=CreatedPost,
        )


__all__ = [
    "Address",
    "Comment",
    "Company",
    "CreatedPost",
    "Geo",
    "JSONPlaceholderClient",
    "Post",
    "Todo",
    "User",
]
