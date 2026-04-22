from __future__ import annotations

import sys
import time
from pathlib import Path

try:
    from .jsonplaceholder_wrapper import JSONPlaceholderClient
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from examples.jsonplaceholder_api.jsonplaceholder_wrapper import JSONPlaceholderClient


def timed(label: str, fn):
    started = time.perf_counter()
    result = fn()
    elapsed_ms = (time.perf_counter() - started) * 1000
    print(f"{label}: {elapsed_ms:.1f} ms")
    return result


def main() -> None:
    client = JSONPlaceholderClient(
        cache_path="jsonplaceholder_cache.json",
        request_log_path="jsonplaceholder_requests.log",
    )

    try:
        post = timed("Fetch post #1", lambda: client.get_post(1))
        print(post.title)
        print()

        cached_post = timed("Fetch post #1 again", lambda: client.get_post(1))
        print(f"Cached title matches: {cached_post.title == post.title}")
        print()

        author = timed("Fetch the post author", lambda: client.get_user(post.user_id))
        print(f"Author: {author.name} <{author.email}>")
        print(f"Company: {author.company.name}")
        print()

        comments = timed("Fetch post comments", lambda: client.list_post_comments(post.id))
        print(f"Comments returned: {len(comments)}")
        print(f"First commenter: {comments[0].email}")
        print()

        todo = timed("Fetch todo #1", lambda: client.get_todo(1))
        print(f"Todo: {todo.title} (completed={todo.completed})")
        print()

        created = timed(
            "Create a demo post",
            lambda: client.create_post(
                user_id=1,
                title="PyperCache demo post",
                body="This POST is not cached and JSONPlaceholder does not persist it.",
            ),
        )
        print(f"Created id: {created.id}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
