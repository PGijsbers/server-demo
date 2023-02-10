import copy
import json

import responses
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from database.models import DatasetDescription
from tests.testutils.paths import path_test_resources

OPENML_URL = "https://www.openml.org/api/v1/json"


def test_happy_path(client: TestClient, engine: Engine):
    dataset_description = DatasetDescription(
        name="anneal", node="openml", node_specific_identifier="1"
    )
    with Session(engine) as session:
        # Populate database.
        # Deepcopy necessary because SqlAlchemy changes the instance so that accessing the
        # node_specific_identifier is not possible anymore
        session.add(copy.deepcopy(dataset_description))
        session.commit()
    with responses.RequestsMock() as mocked_requests:
        _mock_normal_responses(mocked_requests, dataset_description)
        response = client.get("/nodes/openml/datasets/1")
    assert response.status_code == 200
    response_json = response.json()

    with open(path_test_resources() / "connectors" / "openml" / "data_1.json", "r") as f:
        expected_info = json.load(f)["data_set_description"]
    assert response_json["name"] == expected_info["name"]
    assert response_json["description"] == expected_info["description"]
    assert response_json["distribution"]["contentUrl"] == expected_info["url"]
    assert response_json["distribution"]["encodingFormat"] == expected_info["format"]
    assert response_json["size"]["value"] == 898
    assert response_json["includedInDataCatalog"]["name"] == "OpenML"
    assert response_json["identifier"] == "1"


def test_dataset_not_found_in_local_db(client: TestClient, engine: Engine):
    dataset_description = DatasetDescription(
        name="anneal", node="openml", node_specific_identifier="1"
    )
    with Session(engine) as session:
        # Populate database
        session.add(dataset_description)
        session.commit()
    response = client.get("/nodes/openml/datasets/2")  # Note that only dataset 1 exists
    assert response.status_code == 404
    assert response.json()["detail"] == "Dataset '2' of 'openml' not found in the database."


def test_dataset_not_found_in_openml(client: TestClient, engine: Engine):
    dataset_description = DatasetDescription(
        name="anneal", node="openml", node_specific_identifier="1"
    )
    with Session(engine) as session:
        # Populate database
        # Deepcopy necessary because SqlAlchemy changes the instance so that accessing the
        # node_specific_identifier is not possible anymore
        session.add(copy.deepcopy(dataset_description))
        session.commit()
    with responses.RequestsMock() as mocked_requests:
        mocked_requests.add(
            responses.GET,
            f"{OPENML_URL}/data/{dataset_description.node_specific_identifier}",
            json={"error": {"code": "111", "message": "Unknown dataset"}},
            status=412,
        )
        response = client.get("/nodes/openml/datasets/1")
    assert response.status_code == 404
    assert response.json()["detail"] == "Error while fetching data from OpenML: 'Unknown dataset'"


def _mock_normal_responses(
    mocked_requests: responses.RequestsMock, dataset_description: DatasetDescription
):
    """
    Mocking requests to the OpenML dependency, so that we test only our own services
    """
    with open(path_test_resources() / "connectors" / "openml" / "data_1.json", "r") as f:
        data_response = json.load(f)
    with open(path_test_resources() / "connectors" / "openml" / "data_1_qualities.json", "r") as f:
        data_qualities_response = json.load(f)
    mocked_requests.add(
        responses.GET,
        f"{OPENML_URL}/data/{dataset_description.node_specific_identifier}",
        json=data_response,
        status=200,
    )
    mocked_requests.add(
        responses.GET,
        f"{OPENML_URL}/data/qualities/{dataset_description.node_specific_identifier}",
        json=data_qualities_response,
        status=200,
    )
