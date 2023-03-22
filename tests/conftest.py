from typing import List

import mlflow  # type: ignore
import pytest
from globus_sdk import AuthClient, OAuthTokenResponse, SearchClient
from globus_sdk.tokenstorage import SimpleJSONFileAdapter
from mlflow.pyfunc import PyFuncModel  # type: ignore

import garden_ai
from garden_ai import Garden, GardenClient, Pipeline, step


@pytest.fixture(autouse=True)
def do_not_sleep(mocker):
    mocker.patch("time.sleep")


@pytest.fixture(autouse=True)
def do_not_set_mlflow_env_variables(mocker):
    mocker.patch("garden_ai.client.GardenClient._set_up_mlflow_env")


@pytest.fixture
def mock_authorizer_tuple(mocker):
    mock_authorizer = mocker.Mock()
    mock_authorizer_constructor = mocker.patch(
        "garden_ai.client.RefreshTokenAuthorizer", return_value=mock_authorizer
    )
    return mock_authorizer_constructor, mock_authorizer


@pytest.fixture
def identity_jwt():
    return "eyJhbGciOiJSUzUxMiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2YzllMjIzZi1jMjE1LTRjMjYtOWFiYi0yNjJkYmNlMDAwMWMiLCJlbWFpbCI6IndpbGxlbmdsZXJAdWNoaWNhZ28uZWR1IiwibGFzdF9hdXRoZW50aWNhdGlvbiI6MTY3NjU2MjEyNiwiaWRlbnRpdHlfc2V0IjpbeyJzdWIiOiI2YzllMjIzZi1jMjE1LTRjMjYtOWFiYi0yNjJkYmNlMDAwMWMiLCJlbWFpbCI6IndpbGxlbmdsZXJAdWNoaWNhZ28uZWR1IiwibGFzdF9hdXRoZW50aWNhdGlvbiI6MTY3NjU2MjEyNn1dLCJpc3MiOiJodHRwczovL2F1dGguZ2xvYnVzLm9yZyIsImF1ZCI6ImNmOWY4OTM4LWZiNzItNDM5Yy1hNzBiLTg1YWRkZjFiODUzOSIsImV4cCI6MTY3Nzc4NzMzNCwiaWF0IjoxNjc3NjE0NTM0LCJhdF9oYXNoIjoiT1VMX0s3ZmVyNXNBdk03cEI0dXJnNE95dXZVOUxEcGh3SnhCX1VUXzY1cyJ9.TssuMsFeKFQH9Bd29c2Bj0V_f-KkN8alGtHnZOZbg5AQwVPokthHRA4bro7IHuOCXIoh3kX03KPNcLfyRRM5JN1d4SKl0L9KpkJB45BkKzKcg8KPgChOzs_9jRiiDwmXvIpgWiUNVI4grHIEYVpB_VdFdKw6EwWQgu6ZrN_2rvpa45Pc-NZ_-WR4WDFAx2Hak7sXRXslY_1ftlRgV9348uwp78jh1pnXft-mpgpzwqHVALLKgzecCESYmaipWTd3-atczpH9SPIxOn7DoiX2I2Nhn_8IkrhIZnbmtOyY7wINrSGFonN49AncVTNq9AfIngZB26spUByHW4mLB6E2Mw"  # noqa: E501


@pytest.fixture
def token():
    return {
        "refresh_token": "MyRefreshToken",
        "access_token": "MyAccessToken",
        "expires_at_seconds": 1024,
    }


@pytest.fixture
def mock_keystore(mocker):
    mock_keystore = mocker.MagicMock(SimpleJSONFileAdapter)
    mocker.patch("garden_ai.client.SimpleJSONFileAdapter").return_value = mock_keystore
    return mock_keystore


@pytest.fixture
def garden_client(mocker, mock_authorizer_tuple, mock_keystore, token, identity_jwt):
    # blindly stolen from test_client.py test

    # mocker, mock_authorizer_tuple, token, mock_keystore
    mock_authorizer_constructor, mock_authorizer = mock_authorizer_tuple
    # Mocks for KeyStore
    mock_keystore.file_exists.return_value = False

    # Mocks for Login Flow
    mock_auth_client = mocker.MagicMock(AuthClient)
    mock_auth_client.oauth2_get_authorize_url = mocker.Mock(
        return_value="https://globus.auth.garden"
    )
    mock_auth_client.oauth2_start_flow = mocker.Mock()
    # mocker.patch("garden_ai.client.input").return_value = "my token"
    mocker.patch("garden_ai.client.Prompt.ask").return_value = "my token"
    mocker.patch("garden_ai.client.typer.launch")
    mock_search_client = mocker.MagicMock(SearchClient)

    mock_token_response = mocker.MagicMock(OAuthTokenResponse)
    mock_token_response.data = {"id_token": identity_jwt}
    mock_token_response.by_resource_server = {
        "groups.api.globus.org": token,
        "search.api.globus.org": token,
        "0948a6b0-a622-4078-b0a4-bfd6d77d65cf": token,
        "funcx_service": token,
        "auth.globus.org": token,
    }
    mock_auth_client.oauth2_exchange_code_for_tokens = mocker.Mock(
        return_value=mock_token_response
    )

    # Call the Garden constructor
    gc = GardenClient(auth_client=mock_auth_client, search_client=mock_search_client)
    return gc


@pytest.fixture
def garden_title_authors_doi_only():
    pea_garden = Garden(
        authors=["Mendel, Gregor"], title="Experiments on Plant Hybridization"
    )
    pea_garden.doi = "10.26311/fake-doi"
    return pea_garden


@pytest.fixture
def garden_no_fields():
    return Garden()


@pytest.fixture
def pipeline_toy_example(tmp_requirements_txt):
    # define a step using the decorator
    @step(authors=["Sister Constance"])
    def split_peas(ps: List) -> List[tuple]:
        return [(p / 2, p / 2) for p in ps]

    class Soup:
        ...

    @step(authors=["Friar Hugo"])
    def make_soup(splits: List[tuple]) -> Soup:
        return Soup()

    @step(authors=["Abbot Mortimer"], input_info="a spoonful of Soup object")
    def rate_soup(soup_sample: Soup) -> float:
        return 10 / 10

    rate_soup.contributors += ["Friar Hugo", "Sister Constance"]

    pea_edibility_pipeline = Pipeline(
        title="Pea Edibility Pipeline",
        steps=[split_peas, make_soup, rate_soup],
        authors=["Brian Jacques"],
        description="A pipeline for perfectly-reproducible soup ratings.",
        requirements_file=str(tmp_requirements_txt),
    )

    # the complete pipeline is now also callable by itself
    assert pea_edibility_pipeline([1, 2, 3]) == 10 / 10
    return pea_edibility_pipeline


@pytest.fixture
def garden_all_fields(pipeline_toy_example):
    pea_garden = Garden(
        authors=["Mendel, Gregor"],
        title="Experiments on Plant Hybridization",
        contributors=["St. Thomas Abbey"],
    )
    pea_garden.year = "1863"
    pea_garden.language = "en"
    pea_garden.version = "0.0.1"
    pea_garden.description = "This Garden houses ML pipelines for Big Pea Data."
    pea_garden.doi = "10.26311/fake-doi"
    pea_garden.pipelines += [pipeline_toy_example]
    pea_garden.validate()
    return pea_garden


@pytest.fixture
def tmp_requirements_txt(tmp_path):
    """
    Fixture that creates a temporary requirements.txt file
    """
    contents = "Flask==2.1.1\npandas>=1.3.0\nnumpy==1.21.2\nscikit-learn>=0.24.2\n"
    file_path = tmp_path / "requirements.txt"
    with open(file_path, "w") as f:
        f.write(contents)
    return file_path


@pytest.fixture
def tmp_conda_yml(tmp_path):
    """
    Fixture that creates a temporary `conda.yml` file.
    """
    contents = """
    name: my_env
    channels:
      - defaults
    dependencies:
      - python=3.8
      - flask=2.1.1
      - pandas>=1.3.0
      - numpy==1.21.2
      - scikit-learn>=0.24.2
    """
    file_path = tmp_path / "conda.yml"
    with open(file_path, "w") as f:
        f.write(contents)
    return file_path


@pytest.fixture
def step_with_model(mocker, tmp_conda_yml):
    mock_model = mocker.MagicMock(PyFuncModel)
    mock_uri = "models:/email@addr.ess-fake-model/fake-version"

    mock_model_info = mocker.Mock(mlflow.models.model.ModelInfo)
    mock_model_info.model_uri = mock_uri

    mock_model.get_model_info = mocker.Mock()
    mock_model.get_model_info.return_value = mock_model_info

    mocker.patch("garden_ai.mlmodel.load_model").return_value = mock_model

    mocker.patch("garden_ai.steps.get_model_dependencies").return_value = tmp_conda_yml

    @step
    def uses_model_in_default(
        arg: object,
        default_arg_model: object = garden_ai.Model(
            "email@addr.ess-fake-model/fake-version"
        ),
    ) -> object:
        pass

    return uses_model_in_default


@pytest.fixture
def pipeline_using_step_with_model(mocker, tmp_requirements_txt, step_with_model):
    # define a step using the decorator
    @step(authors=["Sister Constance"])
    def split_peas(ps: List) -> List[tuple]:
        return [(p / 2, p / 2) for p in ps]

    class Soup:
        ...

    @step(authors=["Friar Hugo"])
    def make_soup(splits: List[tuple]) -> Soup:
        return Soup()

    ALL_STEPS = (split_peas, make_soup, step_with_model)  # see fixture

    pea_edibility_pipeline = Pipeline(
        title="Pea Edibility Pipeline",
        steps=ALL_STEPS,
        authors=["Brian Jacques"],
        description="A pipeline for perfectly-reproducible soup ratings.",
        requirements_file=str(tmp_requirements_txt),
    )

    return pea_edibility_pipeline
