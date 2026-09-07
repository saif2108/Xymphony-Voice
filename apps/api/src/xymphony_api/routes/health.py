from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from xymphony_api.deps import check_database, get_db_session
from xymphony_api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/v1/health", response_model=HealthResponse)
def health(session: Session = Depends(get_db_session)) -> HealthResponse:
    database = check_database(session)
    return HealthResponse(status="ok", database=database)
