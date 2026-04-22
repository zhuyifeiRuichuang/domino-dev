from fastapi import APIRouter, HTTPException
from clients.airflow_client import AirflowRestClient

router = APIRouter(prefix="/health-check")


@router.get(
    path="",
    status_code=200
)
def health_check():
    """Basic health check for the REST API itself."""
    return {"status": "ok"}


@router.get(
    path="/airflow",
    status_code=200,
    summary="Check Airflow connectivity",
    description=(
        "Verify that the configured Airflow webserver is reachable and responding to API calls. "
        "Returns 200 if healthy, 503 if unreachable."
    ),
)
def airflow_health_check():
    """Check connectivity to the configured Airflow webserver."""
    from core.settings import settings
    client = AirflowRestClient()
    healthy = client.health_check()
    if healthy:
        return {
            "status": "ok",
            "airflow_url": settings.AIRFLOW_WEBSERVER_HOST,
        }
    raise HTTPException(
        status_code=503,
        detail={
            "status": "error",
            "message": f"Airflow webserver at {settings.AIRFLOW_WEBSERVER_HOST} is not reachable or not healthy.",
        },
    )
