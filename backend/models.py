from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, Boolean, Date, Enum,
    ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import TSVECTOR, JSONB, ARRAY
from sqlalchemy.sql import func
from backend.database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    slug = Column(String(255), unique=True, nullable=True)
    logo_url = Column(Text, nullable=True)
    website = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    industry = Column(String(255), nullable=True)
    size = Column(String(100), nullable=True)
    location = Column(String(255), nullable=True)
    # Crawler companies are display-only. Only partners receive applicant data.
    is_partner = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    jobs = relationship("Job", back_populates="company")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    slug = Column(String(255), unique=True, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    jobs = relationship("Job", back_populates="category")


class CareerGuideCategory(Base):
    __tablename__ = "career_guide_categories"
    id = Column(Integer, primary_key=True)
    name = Column(String(150), unique=True, nullable=False)
    slug = Column(String(180), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CareerGuide(Base):
    __tablename__ = "career_guides"
    id = Column(Integer, primary_key=True)
    title = Column(String(300), nullable=False)
    slug = Column(String(340), unique=True, nullable=False, index=True)
    thumbnail_url = Column(Text, nullable=True)
    summary = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    category_id = Column(Integer, ForeignKey("career_guide_categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    author_name = Column(String(255), nullable=True)
    tags = Column(ARRAY(String), nullable=False, default=list)
    status = Column(Enum("draft", "published", "hidden", name="career_guide_status"), nullable=False, server_default="draft")
    is_featured = Column(Boolean, nullable=False, server_default="false")
    view_count = Column(Integer, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    category = relationship("CareerGuideCategory")
    author = relationship("User", foreign_keys=[author_id])


class SavedCareerGuide(Base):
    __tablename__ = "saved_career_guides"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    career_guide_id = Column(Integer, ForeignKey("career_guides.id", ondelete="CASCADE"), nullable=False, index=True)
    saved_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("user_id", "career_guide_id", name="uq_saved_career_guides_user_guide"),)


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job_skills = relationship("JobSkill", back_populates="skill")
    profile_skills = relationship("ProfileSkill", back_populates="skill")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    salary = Column(Text, nullable=True)
    location = Column(Text, nullable=True, index=True)
    experience = Column(Text, nullable=True)
    job_level = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    requirements = Column(Text, nullable=True)
    benefits = Column(Text, nullable=True)
    job_url = Column(Text, unique=True, nullable=False)
    deadline = Column(Text, nullable=True)
    job_type = Column(Text, nullable=True)
    skills = Column(JSONB, nullable=True)
    clean_text = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_time = Column(Text, nullable=True)
    is_ai_labeled = Column(Boolean, default=False)
    conf_score = Column(Float, nullable=True)
    keywords = Column(Text, nullable=True)
    search_vector = Column(TSVECTOR, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    company = relationship("Company", back_populates="jobs")
    category = relationship("Category", back_populates="jobs")
    job_skills = relationship("JobSkill", back_populates="job")

    __table_args__ = (
        Index("idx_jobs_search_vector", "search_vector", postgresql_using="gin"),
        Index("idx_jobs_skills_gin", "skills", postgresql_using="gin"),
        Index("idx_jobs_location", "location"),
        Index("idx_jobs_is_active", "is_active"),
        Index("idx_jobs_created_at", "created_at"),
    )


class JobSkill(Base):
    __tablename__ = "job_skills"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"))
    skill_id = Column(Integer, ForeignKey("skills.id", ondelete="CASCADE"))

    job = relationship("Job", back_populates="job_skills")
    skill = relationship("Skill", back_populates="job_skills")

    __table_args__ = (UniqueConstraint("job_id", "skill_id"),)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone_number = Column(String(32), unique=True, nullable=True, index=True)
    password_hash = Column(Text, nullable=False)
    role = Column(String(50), default="user")
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    data_policy_accepted_at = Column(DateTime(timezone=True), nullable=True)
    data_policy_version = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    profile = relationship("DigitalProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    # ``documents`` has two links to users (owner and verifier).  Pin this
    # relationship to the owner key so SQLAlchemy can configure every mapper.
    documents = relationship(
        "Document",
        foreign_keys="Document.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    consents = relationship("Consent", back_populates="user", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="user", cascade="all, delete-orphan")


class DigitalProfile(Base):
    """Structured CV entered by the applicant; no uploaded CV is processed."""
    __tablename__ = "digital_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    headline = Column(String(255), nullable=True)
    industry = Column(String(255), nullable=True)
    desired_location = Column(String(255), nullable=True)
    desired_job_level = Column(String(100), nullable=True)
    desired_job_type = Column(String(100), nullable=True)
    desired_salary_min = Column(Float, nullable=True)
    desired_salary_max = Column(Float, nullable=True)
    years_experience = Column(Float, nullable=False, default=0)
    education = Column(String(255), nullable=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="profile")
    skills = relationship("ProfileSkill", back_populates="profile", cascade="all, delete-orphan")


class CandidateProfile(Base):
    """Applicant dashboard information entered directly by the account owner."""
    __tablename__ = "candidate_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    nationality = Column(String(100), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(30), nullable=True)
    place_of_birth = Column(String(255), nullable=True)
    marital_status = Column(String(50), nullable=True)
    height_cm = Column(Float, nullable=True)
    weight_kg = Column(Float, nullable=True)
    driving_license_type = Column(String(50), nullable=True)

    contact_address = Column(Text, nullable=True)
    province = Column(String(100), nullable=True)
    ward = Column(String(100), nullable=True)

    education_level = Column(String(100), nullable=True)
    education_grade = Column(String(100), nullable=True)
    specialization = Column(String(255), nullable=True)
    training_institution = Column(String(255), nullable=True)
    foreign_language = Column(String(255), nullable=True)
    foreign_language_school = Column(String(255), nullable=True)
    computer_skill = Column(String(255), nullable=True)
    computer_school = Column(String(255), nullable=True)

    years_experience = Column(Float, nullable=True)
    work_experience = Column(Text, nullable=True)
    workplace = Column(String(255), nullable=True)

    # Never expose or store the identity-document number in plaintext.
    identity_document_number_encrypted = Column(Text, nullable=True)
    identity_issue_date = Column(Date, nullable=True)
    identity_issue_place = Column(String(255), nullable=True)

    religion = Column(String(100), nullable=True)
    ethnicity = Column(String(100), nullable=True)
    employment_status = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ProfileSkill(Base):
    __tablename__ = "profile_skills"

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey("digital_profiles.id", ondelete="CASCADE"), nullable=False)
    skill_id = Column(Integer, ForeignKey("skills.id", ondelete="RESTRICT"), nullable=False)
    proficiency = Column(Integer, nullable=True)  # 1..5, optional so the form stays simple.

    profile = relationship("DigitalProfile", back_populates="skills")
    skill = relationship("Skill", back_populates="profile_skills")
    __table_args__ = (UniqueConstraint("profile_id", "skill_id"),)


class JobSkillRequirement(Base):
    """Normalized JD skills. `required` gets a larger matching weight than `preferred`."""
    __tablename__ = "job_skill_requirements"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id = Column(Integer, ForeignKey("skills.id", ondelete="RESTRICT"), nullable=False)
    importance = Column(Enum("required", "preferred", name="job_skill_importance"), nullable=False, server_default="required")
    tfidf_weight = Column(Float, nullable=False, default=1.0)
    __table_args__ = (UniqueConstraint("job_id", "skill_id"),)


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    doc_type = Column(Enum("personal_profile", "job_application", "health_certificate", "qualification", "identity_card", name="document_type"), nullable=False)
    file_path = Column(Text, nullable=False)  # MinIO object key, never binary data.
    status = Column(Enum("pending", "verified", "rejected", "expired", name="document_status"), nullable=False, server_default="pending")
    is_sensitive = Column(Boolean, nullable=False, default=False)
    # pgcrypto ciphertext for any metadata supplied later (for example ID number).
    # The application never stores or OCRs document content.
    sensitive_metadata_encrypted = Column(Text, nullable=True)
    expiry_date = Column(Date, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    verified_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", foreign_keys=[user_id], back_populates="documents")


class Consent(Base):
    """One row per purpose: consent is deliberately not bundled into a single checkbox."""
    __tablename__ = "consents"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose = Column(Enum("create_profile", "job_recommend", "reuse_documents", "share_with_company", name="consent_purpose"), nullable=False)
    granted_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    consent_text_version = Column(String(50), nullable=False)
    user = relationship("User", back_populates="consents")
    __table_args__ = (UniqueConstraint("user_id", "purpose", name="uq_consents_user_purpose"),)


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(Enum("pending", "accepted", "rejected", "withdrawn", name="application_status"), nullable=False, server_default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    user = relationship("User", back_populates="applications")
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_application_user_job"),)


class ApplicationDocument(Base):
    """A file explicitly attached to one job application."""
    __tablename__ = "application_documents"

    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    __table_args__ = (UniqueConstraint("application_id", "document_id", name="uq_application_documents"),)


class ApplicationFeedback(Base):
    """Recruiter messages delivered to an applicant after reviewing a CV."""
    __tablename__ = "application_feedback"

    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)


class ApplicationShareRequest(Base):
    __tablename__ = "application_share_requests"

    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    requested_doc_types = Column(ARRAY(String), nullable=False, default=list)
    status = Column(Enum("pending", "granted", "declined", "cancelled", name="share_request_status"), nullable=False, server_default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ShareConsentLog(Base):
    """Immutable evidence of the specific data disclosure for one application."""
    __tablename__ = "share_consent_logs"

    id = Column(Integer, primary_key=True)
    share_request_id = Column(Integer, ForeignKey("application_share_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    granted_at = Column(DateTime(timezone=True), server_default=func.now())
    data_shared_snapshot = Column(JSONB, nullable=False)
    ip_address = Column(String(64), nullable=True)


class SearchLog(Base):
    __tablename__ = "search_logs"

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String(500), nullable=True)
    location = Column(String(255), nullable=True)
    category = Column(String(255), nullable=True)
    results_count = Column(Integer, default=0)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


