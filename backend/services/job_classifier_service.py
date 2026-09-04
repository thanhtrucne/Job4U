import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from backend.models import Job, Category
from backend.ml.classifier import JobClassifier

logger = logging.getLogger(__name__)

class JobClassifierService:
    def __init__(self):
        self.classifier = JobClassifier()
        self._category_cache = {}

    async def get_category_id(self, db: AsyncSession, name: str) -> int:
        """Get or create category ID by name."""
        if name in self._category_cache:
            return self._category_cache[name]
        
        result = await db.execute(select(Category).where(Category.name == name))
        cat = result.scalar_one_or_none()
        
        if not cat:
            cat = Category(name=name)
            db.add(cat)
            await db.flush() # Get ID without committing
            
        self._category_cache[name] = cat.id
        return cat.id

    async def classify_job(self, db: AsyncSession, job: Job):
        """Classify a single job and update its fields."""
        if not job.title or not job.description:
            return
            
        category_name, confidence = self.classifier.predict(job.title, job.description)
        
        if category_name:
            cat_id = await self.get_category_id(db, category_name)
            job.category_id = cat_id
            job.conf_score = confidence
            job.is_ai_labeled = True
            logger.info(f"AI Classified Job '{job.title[:30]}' as '{category_name}' (conf: {confidence:.2f})")

    async def classify_all_unlabeled(self, db: AsyncSession):
        """Bulk classify all jobs that haven't been processed by AI yet."""
        result = await db.execute(
            select(Job).where(Job.is_ai_labeled == False)
        )
        jobs = result.scalars().all()
        
        count = 0
        for job in jobs:
            await self.classify_job(db, job)
            count += 1
            
        await db.commit()
        return count

    def get_model_accuracy(self):
        """Return the current model's accuracy from its last evaluation."""
        return self.classifier.get_accuracy()

# Singleton instance
classifier_service = JobClassifierService()
