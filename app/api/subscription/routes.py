from fastapi import APIRouter, Depends, HTTPException, status
import logging
from app.models.subscription import UpgradePlanRequest, UserPlanResponse, PlanType
from app.services.plan_service import PlanService
from app.api.auth.dependencies import get_current_user
from app.models.auth import UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscription", tags=["Subscription"])

@router.get("/plan", response_model=UserPlanResponse)
async def get_user_plan(
    current_user: UserResponse = Depends(get_current_user),
    plan_service: PlanService = Depends(lambda: PlanService())
):
    """Get current user's plan information"""
    logger.info(f"📋 Getting plan info for user: {current_user.email}")
    try:
        plan_info = plan_service.get_user_plan_info(current_user.id)
        logger.info(f"✅ Plan info retrieved - Plan: {plan_info.plan.value}")
        logger.debug(f"   Tokens used: {plan_info.tokens_used_today}/{plan_info.tokens_limit}")
        logger.debug(f"   PDF uploads: {plan_info.pdf_uploads_today}/{plan_info.pdf_uploads_per_day}")
        logger.debug(f"   Images: {plan_info.images_uploaded_today}/{plan_info.images_per_day}")
        return plan_info
    except Exception as e:
        logger.error(f"❌ Failed to get plan info: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get plan information"
        )

@router.post("/upgrade", response_model=UserPlanResponse)
async def upgrade_plan(
    request: UpgradePlanRequest,
    current_user: UserResponse = Depends(get_current_user),
    plan_service: PlanService = Depends(lambda: PlanService())
):
    """Upgrade user's plan"""
    logger.info(f"📈 Upgrade request - User: {current_user.email}, Plan: {request.plan.value}")
    
    if request.plan == PlanType.free:
        logger.warning(f"   ⚠️  Cannot upgrade to free plan")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot upgrade to free plan. Use downgrade endpoint instead."
        )
    
    try:
        success = plan_service.set_user_plan(current_user.id, request.plan)
        if not success:
            logger.error(f"   ❌ Failed to set plan")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upgrade plan"
            )
        
        logger.info(f"✅ Plan upgraded to {request.plan.value} for user: {current_user.email}")
        
        # TODO: Integrate payment processing (Stripe/PayPal) here
        # For now, just update the plan
        logger.info(f"   💳 Payment integration needed for plan: {request.plan.value}")
        
        plan_info = plan_service.get_user_plan_info(current_user.id)
        return plan_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to upgrade plan: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upgrade plan: {str(e)}"
        )

@router.post("/downgrade", response_model=UserPlanResponse)
async def downgrade_plan(
    current_user: UserResponse = Depends(get_current_user),
    plan_service: PlanService = Depends(lambda: PlanService())
):
    """Downgrade user's plan to free"""
    logger.info(f"📉 Downgrade request - User: {current_user.email}")
    
    try:
        success = plan_service.set_user_plan(current_user.id, PlanType.free)
        if not success:
            logger.error(f"   ❌ Failed to set plan")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to downgrade plan"
            )
        
        logger.info(f"✅ Plan downgraded to free for user: {current_user.email}")
        plan_info = plan_service.get_user_plan_info(current_user.id)
        return plan_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to downgrade plan: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to downgrade plan"
        )

