import json
import requests

from garden_ai.gardens import Garden
from globus_sdk import SearchClient, GlobusAPIError
from pydantic import ValidationError

# garden-dev index
GARDEN_INDEX_UUID = "58e4df29-4492-4e7d-9317-b27eba62a911"


class RemoteGardenException(Exception):
    """Exception raised when a requested Garden cannot be found or published"""


def get_remote_garden_by_uuid(
    uuid: str, env_vars: dict, search_client: SearchClient
) -> Garden:
    try:
        res = search_client.get_subject(GARDEN_INDEX_UUID, uuid)
    except GlobusAPIError as e:
        if e.code == 404:
            raise RemoteGardenException(
                f"Could not reach find garden with id {uuid}"
            ) from e
        else:
            raise RemoteGardenException(
                f"Could not reach index {GARDEN_INDEX_UUID}"
            ) from e
    try:
        garden_meta = json.loads(res.text)["entries"][0]["content"]
        garden = Garden(**garden_meta)
    except (ValueError, KeyError, IndexError, ValidationError) as e:
        raise RemoteGardenException(
            f"Could not parse search response {res.text}"
        ) from e
    garden._env_vars = env_vars
    garden._set_pipelines_from_remote_metadata(garden_meta["pipelines"])
    return garden


def get_remote_garden_by_doi(
    doi: str, env_vars: dict, search_client: SearchClient
) -> Garden:
    query = f'(doi: "{doi}")'
    try:
        res = search_client.search(GARDEN_INDEX_UUID, query, advanced=True)
    except GlobusAPIError as e:
        raise RemoteGardenException(f"Could not reach index {GARDEN_INDEX_UUID}") from e
    try:
        parsed_result = json.loads(res.text)
        if parsed_result.get("count", 0) < 1:
            raise RemoteGardenException(f"Could not find garden with doi {doi}")
        garden_meta = parsed_result["gmeta"][0]["entries"][0]["content"]
        garden = Garden(**garden_meta)
    except (ValueError, KeyError, IndexError, ValidationError) as e:
        raise RemoteGardenException(
            f"Could not parse search response {res.text}"
        ) from e
    garden._env_vars = env_vars
    garden._set_pipelines_from_remote_metadata(garden_meta["pipelines"])
    return garden


def publish_garden_metadata(garden: Garden, endpoint: str, header: dict) -> None:
    garden_meta = json.loads(garden.expanded_json())
    res = requests.post(
        f"{endpoint}/garden-search-record", headers=header, json=garden_meta
    )
    if res.status_code >= 400:
        raise RemoteGardenException(
            f"Request to Garden backend to publish garden failed with error: {res.status_code} {res.json()['message']}."
        )
    return None


def search_gardens(query: str, search_client: SearchClient) -> str:
    res = search_client.search(GARDEN_INDEX_UUID, query, advanced=True)
    return res.text
