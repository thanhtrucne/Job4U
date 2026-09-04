from pydantic import BaseModel, HttpUrl, computed_field, field_validator, model_validator
from typing import Optional, List, Literal
from datetime import date, datetime


# â”€â”€ Skill â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class SkillBase(BaseModel):
    name: str

class SkillOut(SkillBase):
    id: int
    model_config = {"from_attributes": True}


# â”€â”€ Company â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class CompanyBase(BaseModel):
    name: str
    slug: Optional[str] = None
    logo_url: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None
    location: Optional[str] = None
    is_partner: bool = False

class CompanyOut(CompanyBase):
    id: int
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}

class CompanyWithJobs(CompanyOut):
    job_count: int = 0


# â”€â”€ Category â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class CategoryBase(BaseModel):
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None

class CategoryOut(CategoryBase):
    id: int
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}

class CategoryWithCount(CategoryOut):
    job_count: int = 0


# â”€â”€ Job â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class JobBase(BaseModel):
    title: str
    salary: Optional[str] = None
    location: Optional[str] = None
    experience: Optional[str] = None
    job_level: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    benefits: Optional[str] = None
    job_url: str
    deadline: Optional[str] = None
    job_type: Optional[str] = None
    created_time: Optional[str] = None

class JobOut(JobBase):
    id: int
    company: Optional[CompanyOut] = None
    category: Optional[CategoryOut] = None
    skills: List[SkillOut] = []
    is_active: bool = True
    is_ai_labeled: bool = False
    conf_score: Optional[float] = None
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}

class JobList(BaseModel):
    id: int
    title: str
    company_name: Optional[str] = None
    company_logo: Optional[str] = None
    salary: Optional[str] = None
    location: Optional[str] = None
    experience: Optional[str] = None
    job_level: Optional[str] = None
    deadline: Optional[str] = None
    job_type: Optional[str] = None
    job_url: str
    created_at: Optional[datetime] = None
    created_time: Optional[str] = None
    is_ai_labeled: bool = False
    conf_score: Optional[float] = None
    category_name: Optional[str] = None # Added for convenience in admin list
    model_config = {"from_attributes": True}

class JobCreate(JobBase):
    company_name: Optional[str] = None
    category_name: Optional[str] = None
    skills: List[str] = []


# â”€â”€ Pagination â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class PaginatedJobs(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    jobs: List[JobList]


# â”€â”€ Stats â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class StatsOut(BaseModel):
    total_jobs: int
    total_companies: int
    total_categories: int
    total_skills: int
    latest_crawled: Optional[datetime] = None


# â”€â”€ Auth â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    name: Optional[str] = None
    email: str
    role: str = "user"

class AdminLogin(BaseModel):
    username: str
    password: str

class UserRegister(BaseModel):
    """Du lieu dang ky tai khoan moi."""
    email: str
    password: str
    confirm_password: str
    full_name: str
    phone_number: str
    data_policy_accepted: bool

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("Email không hợp lệ.")
        return value

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Họ tên phải có ít nhất 2 ký tự.")
        return value

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, value: str) -> str:
        digits = "".join(char for char in value if char.isdigit())
        if len(digits) < 9 or len(digits) > 15:
            raise ValueError("Số điện thoại không hợp lệ.")
        # Store a canonical value so 0901-234-567 and 0901234567 are identical.
        return digits

    @model_validator(mode="after")
    def validate_registration(self):
        if len(self.password) < 8:
            raise ValueError("Mật khẩu phải có ít nhất 8 ký tự.")
        if self.password != self.confirm_password:
            raise ValueError("Mật khẩu nhập lại không khớp.")
        if not self.data_policy_accepted:
            raise ValueError("Bạn cần đồng ý chính sách dữ liệu để tạo tài khoản.")
        return self


class CompanyRegister(UserRegister):
    """Registration data for a company account that can publish portal jobs."""
    company_name: str
    company_website: Optional[str] = None
    company_industry: Optional[str] = None
    company_location: Optional[str] = None

    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Tên doanh nghiệp phải có ít nhất 2 ký tự.")
        return value
class UserLogin(BaseModel):
    """Du lieu dang nhap."""
    email: str
    password: str

class UserOut(BaseModel):
    """Thong tin user tra ve cho client."""
    id: int
    email: str
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    role: str = "user"
    is_active: bool = True
    created_at: Optional[datetime] = None

    @computed_field
    @property
    def name(self) -> Optional[str]:
        return self.full_name

    model_config = {"from_attributes": True}


class CandidateDashboardInput(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    place_of_birth: Optional[str] = None
    marital_status: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    driving_license_type: Optional[str] = None
    contact_address: Optional[str] = None
    province: Optional[str] = None
    ward: Optional[str] = None
    education_level: Optional[str] = None
    education_grade: Optional[str] = None
    specialization: Optional[str] = None
    training_institution: Optional[str] = None
    foreign_language: Optional[str] = None
    foreign_language_school: Optional[str] = None
    computer_skill: Optional[str] = None
    computer_school: Optional[str] = None
    years_experience: Optional[float] = None
    work_experience: Optional[str] = None
    workplace: Optional[str] = None
    identity_document_number: Optional[str] = None
    identity_issue_date: Optional[date] = None
    identity_issue_place: Optional[str] = None
    religion: Optional[str] = None
    ethnicity: Optional[str] = None
    employment_status: Optional[Literal["seeking", "employed", "paused"]] = None
    notes: Optional[str] = None

    @field_validator("height_cm", "weight_kg", "years_experience")
    @classmethod
    def validate_non_negative(cls, value: Optional[float]) -> Optional[float]:
        if value is not None and value < 0:
            raise ValueError("Giá trị không được âm.")
        return value

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Họ tên phải có ít nhất 2 ký tự.")
        return value

    @field_validator("phone_number")
    @classmethod
    def validate_dashboard_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        digits = "".join(char for char in value if char.isdigit())
        if len(digits) < 9 or len(digits) > 15:
            raise ValueError("Số điện thoại không hợp lệ.")
        return digits


class ApplicationFeedbackInput(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = " ".join(value.split())
        if not 2 <= len(value) <= 2000:
            raise ValueError("Nội dung phản hồi phải có từ 2 đến 2.000 ký tự.")
        return value


# Structured CV: values come from the form, never from OCR/PDF extraction.
class ProfileSkillInput(BaseModel):
    skill_id: int
    proficiency: Optional[int] = None


class DigitalProfileInput(BaseModel):
    headline: Optional[str] = None
    industry: Optional[str] = None
    desired_location: Optional[str] = None
    desired_job_level: Optional[str] = None
    desired_job_type: Optional[str] = None
    desired_salary_min: Optional[float] = None
    desired_salary_max: Optional[float] = None
    years_experience: float = 0
    education: Optional[str] = None
    summary: Optional[str] = None
    skills: List[ProfileSkillInput] = []
    policy_accepted: bool = False


class ConsentInput(BaseModel):
    purpose: Literal["create_profile", "job_recommend", "reuse_documents", "share_with_company"]
    granted: bool
    consent_text_version: str


# â”€â”€ Search â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class SearchParams(BaseModel):
    keyword: Optional[str] = None
    location: Optional[str] = None
    category: Optional[str] = None
    company: Optional[str] = None
    skill: Optional[str] = None
    page: int = 1
    page_size: int = 20
