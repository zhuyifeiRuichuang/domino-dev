"""
Airflow REST API client.

Supports Airflow 2.x (2.0 – 2.10+).

Configuration:
    AIRFLOW_WEBSERVER_HOST  - base URL (e.g. http://airflow-webserver:8080 or http://192.168.1.10:8080)
    AIRFLOW_ADMIN_USERNAME  - login username
    AIRFLOW_ADMIN_PASSWORD  - login password

The client transparently handles minor API differences between Airflow versions.
"""

from __future__ import annotations

import ast
import uuid
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import requests
from aiohttp import BasicAuth

from core.logger import get_configured_logger
from core.settings import settings
from schemas.exceptions.base import ResourceNotFoundException


class AirflowRestClient(requests.Session):
    """
    Session-based client for the Airflow Stable REST API (api/v1).

    The base URL is taken from ``settings.AIRFLOW_WEBSERVER_HOST``.
    Credentials are taken from ``settings.AIRFLOW_ADMIN_CREDENTIALS``.

    Both can be overridden at construction time to support multiple Airflow
    instances or custom configurations.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.base_url = (base_url or settings.AIRFLOW_WEBSERVER_HOST).rstrip("/")
        _username = username or settings.AIRFLOW_ADMIN_CREDENTIALS.get("username", "admin")
        _password = password or settings.AIRFLOW_ADMIN_CREDENTIALS.get("password", "admin")
        self.auth = (_username, _password)
        self.logger = get_configured_logger(self.__class__.__name__)

        self.max_page_size = 100
        self.min_page_size = 1
        self.min_page = 0

    # ------------------------------------------------------------------
    # Core request helpers
    # ------------------------------------------------------------------

    def _validate_pagination_params(self, page: int, page_size: int):
        page = max(page, self.min_page)
        page_size = max(self.min_page_size, min(page_size, self.max_page_size))
        return page, page_size

    def request(self, method: str, resource: str, **kwargs):
        """Override requests.Session.request to auto-prefix the base URL."""
        try:
            # Allow callers to pass a full URL (starts with http) or a path
            if resource.startswith("http"):
                url = resource
            else:
                url = f"{self.base_url}/{resource.lstrip('/')}"
            return super().request(method, url, **kwargs)
        except requests.exceptions.ConnectionError as exc:
            self.logger.error("Airflow connection error: %s", exc)
            raise exc
        except Exception as exc:
            self.logger.exception(exc)
            raise exc

    async def _request_async(self, session, method: str, resource: str, **kwargs):
        """Async variant used for concurrent DAG status checks."""
        try:
            if resource.startswith("http"):
                url = resource
            else:
                url = f"{self.base_url}/{resource.lstrip('/')}"
            auth = BasicAuth(*self.auth)
            response = await session.request(method, url, auth=auth, **kwargs)
            response.raise_for_status()
        except Exception:
            self.logger.exception("Async API %s error. Url: %s. Params: %s", method, resource, kwargs)
            return None
        return await response.json()

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health_check(self) -> bool:
        """Return True if the Airflow webserver is reachable and healthy."""
        try:
            resp = self.request("get", "api/v1/health")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("status") == "healthy" or "metadatabase" in data
            return False
        except Exception as exc:
            self.logger.warning("Airflow health check failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # DAG management
    # ------------------------------------------------------------------

    def run_dag(self, dag_id: str):
        resource = f"api/v1/dags/{dag_id}/dagRuns"
        dag_run_uuid = str(uuid.uuid4())
        payload = {
            "dag_run_id": f"rest-client-{dag_run_uuid}",
            "logical_date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        return self.request("post", resource, json=payload)

    def delete_dag(self, dag_id: str):
        resource = f"api/v1/dags/{dag_id}"
        return self.request("delete", resource)

    def update_dag(self, dag_id: str, payload: dict):
        resource = f"api/v1/dags/{dag_id}"
        return self.request("patch", resource, json=payload)

    def get_dag_by_id(self, dag_id: str):
        resource = f"api/v1/dags/{dag_id}"
        return self.request("get", resource)

    async def get_dag_by_id_async(self, session, dag_id: str):
        resource = f"api/v1/dags/{dag_id}"
        response = await self._request_async(session, "GET", resource)
        return {"dag_id": dag_id, "response": response}

    def get_all_dag_tasks(self, dag_id: str):
        resource = f"api/v1/dags/{dag_id}/tasks"
        return self.request("get", resource)

    # ------------------------------------------------------------------
    # Import errors
    # ------------------------------------------------------------------

    def list_import_errors(self, limit: int = 100, offset: int = 0):
        resource = "api/v1/importErrors"
        return self.request("get", resource, params={"limit": limit, "offset": offset})

    # ------------------------------------------------------------------
    # DAG runs
    # ------------------------------------------------------------------

    def get_all_workflow_runs(
        self,
        dag_id: str,
        page: int,
        page_size: int,
        descending: bool = False,
    ):
        page, page_size = self._validate_pagination_params(page, page_size)
        offset = page * page_size
        order_by = "-execution_date" if descending else "execution_date"
        resource = (
            f"api/v1/dags/{dag_id}/dagRuns"
            f"?limit={page_size}&offset={offset}&order_by={order_by}"
        )
        return self.request("get", resource)

    def get_all_run_tasks_instances(
        self,
        dag_id: str,
        dag_run_id: str,
        page: int,
        page_size: int,
    ):
        page, page_size = self._validate_pagination_params(page, page_size)
        offset = page * page_size
        resource = (
            f"api/v1/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances"
            f"?limit={page_size}&offset={offset}"
        )
        return self.request("get", resource)

    # ------------------------------------------------------------------
    # Task logs & results
    # ------------------------------------------------------------------

    def get_task_logs(
        self,
        dag_id: str,
        dag_run_id: str,
        task_id: str,
        task_try_number: int,
    ):
        resource = (
            f"api/v1/dags/{dag_id}/dagRuns/{dag_run_id}"
            f"/taskInstances/{task_id}/logs/{task_try_number}"
        )
        response = self.request("get", resource)
        if response.status_code == 404:
            raise ResourceNotFoundException("Task result not found.")
        return response

    def get_task_result(
        self,
        dag_id: str,
        dag_run_id: str,
        task_id: str,
        task_try_number: int,
    ):
        """
        Fetch XCom ``return_value`` for a task.

        Compatible with Airflow 2.x: the XCom endpoint path and the value
        encoding (base64 in 2.7+) are handled transparently.
        """
        resource = (
            f"api/v1/dags/{dag_id}/dagRuns/{dag_run_id}"
            f"/taskInstances/{task_id}/xcomEntries/return_value"
        )
        response = self.request("get", resource)
        if response.status_code == 404:
            raise ResourceNotFoundException("Task result not found.")
        if response.status_code != 200:
            raise Exception("Error while trying to get task result base64_content")

        raw_value = response.json().get("value")
        if raw_value is None:
            return {}

        # Airflow 2.7+ may return the value already as a dict/serialised JSON,
        # while older versions return a string representation of a dict.
        if isinstance(raw_value, dict):
            response_dict = raw_value
        else:
            try:
                response_dict = ast.literal_eval(raw_value)
            except (ValueError, SyntaxError):
                import json as _json
                try:
                    response_dict = _json.loads(raw_value)
                except Exception:
                    self.logger.warning("Could not parse XCom value: %s", raw_value[:200])
                    return {}

        result_dict = {}
        if "display_result" in response_dict:
            result_dict["base64_content"] = response_dict["display_result"].get("base64_content")
            result_dict["file_type"] = response_dict["display_result"].get("file_type")
        return result_dict

    # ------------------------------------------------------------------
    # schedule_interval compatibility shim
    # ------------------------------------------------------------------

    @staticmethod
    def extract_schedule(dag_info: dict) -> Optional[str]:
        """
        Extract the schedule value from a dag info dict in a version-safe way.

        - Airflow < 2.4: ``schedule_interval``
        - Airflow >= 2.4: ``schedule_interval`` is deprecated but still present
          in the API response (as a dict with ``value`` key or a plain string).
        - Airflow 2.9+: ``timetable_summary`` may replace it.
        """
        schedule = dag_info.get("schedule_interval") or dag_info.get("timetable_summary")
        if isinstance(schedule, dict):
            return schedule.get("value")
        return schedule
