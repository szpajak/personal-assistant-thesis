from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    secret_key: str
    environment: str = "development"
    database_url: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    redis_url: str
    postgres_user: str | None = "user"
    postgres_password: str | None = "password"
    postgres_db: str | None = "career_assistant"
    deepseek_api_key: str
    deepseek_chat_model: str = "deepseek-v4-flash"
    huggingface_embedding_model: str = "all-MiniLM-L6-v2"
    huggingface_embedding_dimension: int = 384
    imap_host: str
    imap_port: int
    imap_user: str
    imap_password: str
    # Verify the IMAP server's TLS certificate. Set to false only for trusted
    # internal servers using a self-signed certificate.
    imap_verify_ssl: bool = True
    # Optional path to a CA bundle used to verify a self-signed IMAP certificate.
    imap_ca_file: str | None = None
    next_public_api_base_url: str | None = None
    # The app is single-primary-user oriented today (one IMAP mailbox, one
    # portfolio owner). Background jobs that have no authenticated request
    # context (email polling, market-demand snapshots) attribute their
    # writes to this Person id. Prefer ``user_{postgres_id}`` (see setup_kg /
    # email_tasks) over the legacy seed id ``u1``.
    primary_person_id: str = "u1"

    # Global job scraping configuration
    job_search_terms: str = "Python Developer,Software Engineer"
    job_search_location: str = "Remote"
    job_search_sites: str = "linkedin,indeed"
    job_results_wanted: int = 25
    job_scrape_ttl_days: int = 7
    # Soft daily cap on LLM job-match calls per person (Redis counter). This
    # guards against a runaway bug/loop, not against provider scarcity - at
    # DeepSeek's pay-as-you-go pricing 300 calls/day is still well under $1.
    llm_match_daily_limit: int = 300
    # When batch-matching many career offers, only LLM-score the top K
    # after free overlap + local embedding shortlist.
    llm_match_batch_top_k: int = 25
    llm_match_batch_max: int = 50
    job_linkedin_fetch_description: bool = True
    job_country_indeed: str = "USA"
    job_proxies: str = ""
    job_scrape_remoteok: bool = False
    # Rate limiting for LinkedIn/Indeed scraping (via jobspy2): results are
    # fetched in small batches with a sleep in between, and retried with
    # exponential backoff on failure, instead of one big burst request that
    # is what typically gets an IP flagged/blocked by LinkedIn.
    job_scrape_batch_size: int = 25
    job_scrape_sleep_seconds: int = 30
    job_scrape_max_retries: int = 3

    @field_validator("job_search_terms", "job_search_sites", mode="before")
    @classmethod
    def _strip_job_list_fields(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @property
    def job_search_terms_list(self) -> list[str]:
        return [
            term.strip() for term in self.job_search_terms.split(",") if term.strip()
        ]

    @property
    def job_search_sites_list(self) -> list[str]:
        return [
            site.strip() for site in self.job_search_sites.split(",") if site.strip()
        ]

    @property
    def job_proxies_list(self) -> list[str]:
        return [proxy.strip() for proxy in self.job_proxies.split(",") if proxy.strip()]

    class Config:
        env_file = ".env"


settings: Settings = Settings()  # type: ignore[call-arg]
