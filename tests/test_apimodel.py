from PyperCache.models.apimodel import apimodel
from PyperCache.utils.typing_cast import instantiate_type
from PyperCache.core.cache import Cache


def test_apimodel_hydrates_and_registers():
    @apimodel
    class User:
        id: int
        name: str
        email: str

    data = {"id": 1, "name": "Alice", "email": "alice@example.com"}

    cache = Cache(filepath=None)
    cache.store("u:1", data, cast=User)

    obj = cache.get_object("u:1")
    assert isinstance(obj, User)
    assert obj.id == 1
    assert obj.name == "Alice"


def test_instantiate_type_handles_list_of_apimodels():
    @apimodel
    class User:
        id: int
        name: str

    payload = [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
    ]

    result = instantiate_type(list[User], payload)
    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(x, User) for x in result)
    assert result[1].name == "Bob"
