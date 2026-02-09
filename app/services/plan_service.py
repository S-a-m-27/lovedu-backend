import os
import logging
from typing import Optional, Tuple
from datetime import date, datetime, timedelta
from supabase import create_client
from app.models.subscription import PlanType, PlanDetails, UserUsageResponse, UserPlanResponse

logger = logging.getLogger(__name__)

class PlanService:
    _instance: Optional['PlanService'] = None
    _supabase_client = None
    
    PLAN_LIMITS = {
        PlanType.free: PlanDetails(
            plan=PlanType.free,
            tokens_limit=2000,
            pdf_uploads_per_day=3,
            images_per_day=3,
            price_per_month=0.0
        ),
        PlanType.basic: PlanDetails(
            plan=PlanType.basic,
            tokens_limit=2000000,  # 2M tokens
            pdf_uploads_per_day=20,
            images_per_day=20,
            price_per_month=10.0
        ),
        PlanType.pro: PlanDetails(
            plan=PlanType.pro,
            tokens_limit=-1,  # Unlimited
            pdf_uploads_per_day=-1,  # Unlimited
            images_per_day=-1,  # Unlimited
            price_per_month=None  # Contact for pricing
        )
    }
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PlanService, cls).__new__(cls)
        return cls._instance
    
    def _get_supabase_client(self):
        """Get Supabase service role client"""
        if self._supabase_client is None:
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            
            logger.debug(f"📋 SUPABASE_URL: {supabase_url if supabase_url else 'NOT SET'}")
            if supabase_service_key:
                masked_key = supabase_service_key[:10] + "..." + supabase_service_key[-4:] if len(supabase_service_key) > 14 else "***"
                logger.debug(f"📋 SUPABASE_SERVICE_ROLE_KEY: {masked_key} (loaded)")
            else:
                logger.error("❌ SUPABASE_SERVICE_ROLE_KEY: NOT SET")
            
            if not supabase_url or not supabase_service_key:
                error_msg = "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set"
                logger.error(f"❌ {error_msg}")
                raise ValueError(error_msg)
            
            self._supabase_client = create_client(supabase_url, supabase_service_key)
            logger.info("✅ Supabase service client created for PlanService")
        
        return self._supabase_client
    
    def get_plan_details(self, plan: PlanType) -> PlanDetails:
        """Get plan details by plan type"""
        return self.PLAN_LIMITS.get(plan, self.PLAN_LIMITS[PlanType.free])
    
    def get_user_plan(self, user_id: str) -> PlanType:
        """Get user's current plan from user_metadata"""
        logger.info(f"📋 Getting plan for user: {user_id}")
        try:
            client = self._get_supabase_client()
            response = client.auth.admin.get_user_by_id(user_id)
            
            if response.user:
                user_metadata = response.user.user_metadata or {}
                plan_str = user_metadata.get("plan", "free")
                try:
                    plan = PlanType(plan_str)
                    logger.debug(f"   User plan: {plan.value}")
                    return plan
                except ValueError:
                    logger.warning(f"   Invalid plan '{plan_str}' in metadata, defaulting to free")
                    return PlanType.free
            
            logger.warning(f"   User not found, defaulting to free plan")
            return PlanType.free
        except Exception as e:
            logger.error(f"❌ Failed to get user plan: {str(e)}")
            logger.exception("Full error traceback:")
            return PlanType.free
    
    def set_user_plan(self, user_id: str, plan: PlanType) -> bool:
        """Set user's plan in user_metadata"""
        logger.info(f"📝 Setting plan {plan.value} for user: {user_id}")
        try:
            client = self._get_supabase_client()
            
            # Get current user metadata
            user_response = client.auth.admin.get_user_by_id(user_id)
            if not user_response.user:
                logger.error(f"   ❌ User not found: {user_id}")
                return False
            
            current_metadata = user_response.user.user_metadata or {}
            current_metadata["plan"] = plan.value
            
            # Update user metadata
            client.auth.admin.update_user_by_id(
                user_id,
                {"user_metadata": current_metadata}
            )
            
            # Update or create subscription record
            self._update_subscription_record(user_id, plan)
            
            logger.info(f"✅ Plan {plan.value} set for user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to set user plan: {str(e)}")
            logger.exception("Full error traceback:")
            return False
    
    def _update_subscription_record(self, user_id: str, plan: PlanType):
        """Update subscription record in database"""
        try:
            client = self._get_supabase_client()
            
            # Check if subscription exists
            existing = client.table("user_subscriptions").select("*").eq("user_id", user_id).execute()
            
            subscription_data = {
                "user_id": user_id,
                "plan": plan.value,
                "status": "active",
                "updated_at": datetime.utcnow().isoformat()
            }
            
            if plan != PlanType.free:
                # Set period for paid plans (30 days)
                now = datetime.utcnow()
                subscription_data["current_period_start"] = now.isoformat()
                subscription_data["current_period_end"] = (now + timedelta(days=30)).isoformat()
            
            if existing.data and len(existing.data) > 0:
                # Update existing
                client.table("user_subscriptions").update(subscription_data).eq("user_id", user_id).execute()
                logger.debug(f"   Subscription record updated for user: {user_id}")
            else:
                # Create new
                client.table("user_subscriptions").insert(subscription_data).execute()
                logger.debug(f"   Subscription record created for user: {user_id}")
            
        except Exception as e:
            logger.error(f"   ⚠️  Failed to update subscription record: {str(e)}")
            logger.exception("Full error traceback:")
    
    def get_user_usage_today(self, user_id: str) -> UserUsageResponse:
        """Get user's usage for today"""
        logger.debug(f"📊 Getting today's usage for user: {user_id}")
        try:
            client = self._get_supabase_client()
            today = date.today().isoformat()
            
            response = client.table("user_usage").select("*").eq("user_id", user_id).eq("usage_date", today).execute()
            
            if response.data and len(response.data) > 0:
                usage = response.data[0]
                return UserUsageResponse(
                    user_id=usage["user_id"],
                    usage_date=usage["usage_date"],
                    tokens_used=usage["tokens_used"],
                    pdf_uploads=usage["pdf_uploads"],
                    images_uploaded=usage["images_uploaded"]
                )
            
            # Return zero usage if no record exists
            return UserUsageResponse(
                user_id=user_id,
                usage_date=today,
                tokens_used=0,
                pdf_uploads=0,
                images_uploaded=0
            )
        except Exception as e:
            logger.error(f"❌ Failed to get user usage: {str(e)}")
            logger.exception("Full error traceback:")
            return UserUsageResponse(
                user_id=user_id,
                usage_date=date.today().isoformat(),
                tokens_used=0,
                pdf_uploads=0,
                images_uploaded=0
            )
    
    def increment_usage(self, user_id: str, tokens: int = 0, pdf_uploads: int = 0, images: int = 0):
        """Increment user's daily usage"""
        logger.debug(f"📈 Incrementing usage for user: {user_id} - Tokens: {tokens}, PDFs: {pdf_uploads}, Images: {images}")
        try:
            client = self._get_supabase_client()
            today = date.today().isoformat()
            
            # Get current usage
            current = self.get_user_usage_today(user_id)
            
            # Upsert usage record
            usage_data = {
                "user_id": user_id,
                "usage_date": today,
                "tokens_used": current.tokens_used + tokens,
                "pdf_uploads": current.pdf_uploads + pdf_uploads,
                "images_uploaded": current.images_uploaded + images,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Check if record exists
            existing = client.table("user_usage").select("id").eq("user_id", user_id).eq("usage_date", today).execute()
            
            if existing.data and len(existing.data) > 0:
                client.table("user_usage").update(usage_data).eq("user_id", user_id).eq("usage_date", today).execute()
            else:
                client.table("user_usage").insert(usage_data).execute()
            
            logger.debug(f"   ✅ Usage updated for user: {user_id}")
        except Exception as e:
            logger.error(f"❌ Failed to increment usage: {str(e)}")
            logger.exception("Full error traceback:")
    
    def check_usage_limit(self, user_id: str, tokens_needed: int = 0, pdf_needed: int = 0, images_needed: int = 0) -> Tuple[bool, str]:
        """
        Check if user can perform action based on plan limits
        Returns: (can_proceed: bool, error_message: str)
        """
        plan = self.get_user_plan(user_id)
        plan_details = self.get_plan_details(plan)
        usage = self.get_user_usage_today(user_id)
        
        # Pro plan has unlimited everything
        if plan == PlanType.pro:
            logger.debug(f"   ✅ Pro plan - unlimited access")
            return True, ""
        
        # Check tokens
        if plan_details.tokens_limit > 0:
            if usage.tokens_used + tokens_needed > plan_details.tokens_limit:
                error_msg = f"Token limit exceeded. You have used {usage.tokens_used}/{plan_details.tokens_limit} tokens today."
                logger.warning(f"   ⚠️  {error_msg}")
                return False, error_msg
        
        # Check PDF uploads
        if plan_details.pdf_uploads_per_day > 0:
            if usage.pdf_uploads + pdf_needed > plan_details.pdf_uploads_per_day:
                error_msg = f"PDF upload limit exceeded. You have uploaded {usage.pdf_uploads}/{plan_details.pdf_uploads_per_day} PDFs today."
                logger.warning(f"   ⚠️  {error_msg}")
                return False, error_msg
        
        # Check images
        if plan_details.images_per_day > 0:
            if usage.images_uploaded + images_needed > plan_details.images_per_day:
                error_msg = f"Image upload limit exceeded. You have uploaded {usage.images_uploaded}/{plan_details.images_per_day} images today."
                logger.warning(f"   ⚠️  {error_msg}")
                return False, error_msg
        
        logger.debug(f"   ✅ Usage check passed")
        return True, ""
    
    def get_user_plan_info(self, user_id: str) -> UserPlanResponse:
        """Get comprehensive plan information for user"""
        plan = self.get_user_plan(user_id)
        plan_details = self.get_plan_details(plan)
        usage = self.get_user_usage_today(user_id)
        
        tokens_remaining = -1  # Unlimited
        if plan_details.tokens_limit > 0:
            tokens_remaining = max(0, plan_details.tokens_limit - usage.tokens_used)
        
        return UserPlanResponse(
            plan=plan,
            tokens_limit=plan_details.tokens_limit,
            pdf_uploads_per_day=plan_details.pdf_uploads_per_day,
            images_per_day=plan_details.images_per_day,
            tokens_used_today=usage.tokens_used,
            pdf_uploads_today=usage.pdf_uploads,
            images_uploaded_today=usage.images_uploaded,
            tokens_remaining=tokens_remaining,
            price_per_month=plan_details.price_per_month
        )

