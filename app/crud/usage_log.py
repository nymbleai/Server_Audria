from typing import List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from datetime import datetime

from app.crud.base import CRUDBase
from app.models.usage_log import UsageLog, FeatureType
from app.schemas.billing import UsageLogCreate, UsageLogUpdate


class CRUDUsageLog(CRUDBase[UsageLog, UsageLogCreate, UsageLogUpdate]):
    async def exists_by_request_id(
        self,
        db: AsyncSession,
        user_id: str,
        feature_type: FeatureType,
        request_id: str
    ) -> bool:
        """Check if a usage_log entry already exists for a given request_id/user/feature."""
        if not request_id:
            return False
        query = select(func.count(self.model.id)).where(
            and_(
                self.model.supabase_user_id == user_id,
                self.model.feature_used == feature_type,
                self.model.request_id == request_id,
                self.model.is_deleted == False
            )
        )
        result = await db.execute(query)
        return (result.scalar() or 0) > 0

    async def get_by_user_id_and_period(
        self, 
        db: AsyncSession, 
        user_id: str,
        start_date: datetime,
        end_date: datetime,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[UsageLog], int]:
        """Get usage logs for a user within a date range"""
        query = select(self.model).where(
            and_(
                self.model.supabase_user_id == user_id,
                self.model.created_at >= start_date,
                self.model.created_at <= end_date,
                self.model.is_deleted == False
        )).order_by(desc(self.model.created_at))
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        items = result.scalars().all()
        
        return items, total
    
    async def get_usage_summary(
        self, 
        db: AsyncSession, 
        user_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> dict:
        """Get aggregated usage summary for a user within a date range"""
        result = await db.execute(
            select(
                func.sum(self.model.tokens_used).label('total_tokens'),
                func.sum(self.model.dollar_cost).label('total_cost'),
                func.count(self.model.id).label('total_requests')
            )
            .where(
                and_(
                    self.model.supabase_user_id == user_id,
                    self.model.created_at >= start_date,
                    self.model.created_at <= end_date,
                    self.model.is_deleted == False
                )
            )
        )
        
        row = result.first()
        return {
            'total_tokens': row.total_tokens or 0,
            'total_cost': float(row.total_cost or 0.0),
            'total_requests': row.total_requests or 0
        }
    
    async def get_by_feature_type(
        self, 
        db: AsyncSession, 
        user_id: str,
        feature_type: FeatureType,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[UsageLog], int]:
        """Get usage logs for a specific feature type"""
        return await self.get_multi(
            db,
            skip=skip,
            limit=limit,
            filters={
                'supabase_user_id': user_id,
                'feature_used': feature_type
            }
        )


usage_log = CRUDUsageLog(UsageLog)

