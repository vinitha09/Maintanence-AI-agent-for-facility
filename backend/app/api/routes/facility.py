from fastapi import APIRouter

from backend.app.api.routes.admin import router as admin_router
from backend.app.api.routes.auth import router as auth_router
from backend.app.api.routes.maintenance_logs import (
    router as maintenance_logs_router,
)
from backend.app.api.routes.facilities import router as facilities_router
from backend.app.api.routes.hierarchy import router as hierarchy_router
from backend.app.api.routes.machines import router as machines_router
from backend.app.api.routes.manuals import router as manuals_router
from backend.app.api.routes.organizations import router as organizations_router
from backend.app.api.routes.rag import router as rag_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(admin_router)
router.include_router(organizations_router)
router.include_router(facilities_router)
router.include_router(hierarchy_router)
router.include_router(machines_router)
router.include_router(manuals_router)
router.include_router(maintenance_logs_router)
router.include_router(rag_router)
