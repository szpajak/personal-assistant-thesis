import asyncio
import logging
import os

from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.kg.repository import KGRepository
from app.models.user import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def setup_postgres() -> User | None:
    """Seed default user in Postgres and return that user (existing or new)."""
    logger.info("Checking for default user in Postgres...")
    async with async_session_factory() as session:
        try:
            # Check if user exists
            query = select(User).where(User.email == "test@example.com")
            result = await session.execute(query)
            user = result.scalar_one_or_none()

            if not user:
                logger.info("Creating default user 'test@example.com'...")
                new_user = User(
                    email="test@example.com",
                    hashed_password=hash_password("password123"),
                    full_name="Test User",
                )
                session.add(new_user)
                await session.commit()
                await session.refresh(new_user)
                logger.info("Default user created successfully.")
                return new_user

            logger.info("Default user already exists.")
            return user
        except Exception as e:
            logger.error(f"Failed to seed Postgres user: {e}")
            await session.rollback()
            return None


async def setup_indexes(repo: KGRepository):
    """Create vector indexes if they don't exist."""
    logger.info("Verifying vector indexes...")

    indexes = [
        ("project_embedding_index", "Project"),
        ("skill_embedding_index", "Skill"),
        ("joboffer_embedding_index", "JobOffer"),
        ("certificate_embedding_index", "Certificate"),
    ]

    for index_name, label in indexes:
        try:
            # Check if index exists
            check_query = f"SHOW INDEXES WHERE name = '{index_name}'"
            res = await repo.query(check_query)

            if not res:
                logger.info(f"Creating vector index: {index_name}")
                # Use the procedure call which is more compatible across Neo4j 5.x versions
                create_query = f"CALL db.index.vector.createNodeIndex('{index_name}', '{label}', 'embedding', 384, 'cosine')"
                await repo.query(create_query)
            else:
                logger.info(f"Index already exists: {index_name}")
        except Exception as e:
            logger.error(f"Failed to create index {index_name}: {e}")


async def setup_fulltext_indexes(repo: KGRepository):
    """Create the Lucene full-text indexes GraphRAG's hybrid retrieval relies on.

    ``backend/app/kg/repository.py``'s ``fulltext_search`` computes the index
    name as ``f"{label.lower()}_fulltext_index"`` and silently degrades to
    vector-only search when the index doesn't exist - these mirror that exact
    naming so every hybrid-search label actually has a working index. This was
    previously only declared in ``infra/neo4j/init.cypher``, which is mounted
    at ``/docker-entrypoint-initdb.d/`` - a PostgreSQL convention that Neo4j
    never executes, so the indexes were never actually created.
    """
    logger.info("Verifying full-text indexes...")

    fulltext_indexes = [
        ("project_fulltext_index", "Project", ["title", "description"]),
        ("skill_fulltext_index", "Skill", ["name", "category"]),
        ("joboffer_fulltext_index", "JobOffer", ["title", "description"]),
        ("certificate_fulltext_index", "Certificate", ["title", "issuer"]),
    ]

    for index_name, label, properties in fulltext_indexes:
        try:
            props = ", ".join(f"n.{prop}" for prop in properties)
            create_query = (
                f"CREATE FULLTEXT INDEX {index_name} IF NOT EXISTS "
                f"FOR (n:{label}) ON EACH [{props}]"
            )
            await repo.query(create_query)
            logger.info(f"Verified full-text index: {index_name}")
        except Exception as e:
            logger.error(f"Failed to create full-text index {index_name}: {e}")


async def setup_schema(repo: KGRepository):
    """Register expected labels and relationship types in the schema.

    On a fresh database the read queries (applications, market demand, related
    nodes, skill analysis) reference labels/relationship types that no node has
    created yet, so Neo4j floods the logs with "unknown label/relationship type"
    warnings. Creating then deleting a temporary subgraph registers those tokens
    in the schema, which silences the warnings without leaving real data behind.
    """
    logger.info("Registering KG schema tokens...")

    seed_query = """
    MERGE (p:Person {id: '__schema_seed_person'})
    MERGE (a:Application {id: '__schema_seed_application'})
    MERGE (j:JobOffer {id: '__schema_seed_joboffer'})
    SET j.status = 'active'
    MERGE (s:Skill {id: '__schema_seed_skill'})
    MERGE (pr:Project {id: '__schema_seed_project'})
    MERGE (c:Certificate {id: '__schema_seed_certificate'})
    MERGE (comp:Company {id: '__schema_seed_company'})
    MERGE (em:Email {id: '__schema_seed_email'})
    MERGE (lr:LearningResource {id: '__schema_seed_learning'})
    MERGE (doc:Document {id: '__schema_seed_document'})
    MERGE (emp:Employment {id: '__schema_seed_employment'})
    MERGE (edu:Education {id: '__schema_seed_education'})
    MERGE (tr:TargetRole {id: '__schema_seed_target_role'})
    MERGE (snap:SkillDemandSnapshot {id: '__schema_seed_snapshot'})
    MERGE (p)-[:APPLIED_TO]->(a)
    MERGE (a)-[:FOR_OFFER]->(j)
    MERGE (p)-[:HAS_SKILL]->(s)
    MERGE (p)-[:PRODUCED]->(pr)
    MERGE (pr)-[:USES]->(s)
    MERGE (j)-[:REQUIRES]->(s)
    MERGE (j)-[:POSTED_BY]->(comp)
    MERGE (p)-[:SAVED]->(j)
    MERGE (p)-[:HAS_CERTIFICATE]->(c)
    MERGE (c)-[:VALIDATES]->(s)
    MERGE (p)-[:RECEIVED]->(em)
    MERGE (a)-[:HAS_EMAIL]->(em)
    MERGE (em)-[:FROM_COMPANY]->(comp)
    MERGE (lr)-[:TEACHES]->(s)
    MERGE (p)-[:RECOMMENDED]->(lr)
    MERGE (p)-[:WORKED_AT]->(emp)
    MERGE (emp)-[:AT_COMPANY]->(comp)
    MERGE (emp)-[:USED_IN_ROLE]->(s)
    MERGE (p)-[:STUDIED_AT]->(edu)
    MERGE (p)-[:AIMS_FOR]->(tr)
    MERGE (tr)-[:REQUIRES]->(s)
    MERGE (s)-[:DEMAND_SNAPSHOT]->(snap)
    """
    cleanup_query = """
    MATCH (n) WHERE n.id STARTS WITH '__schema_seed_' DETACH DELETE n
    """

    try:
        await repo.query(seed_query)
        await repo.query(cleanup_query)
        logger.info("KG schema tokens registered.")
    except Exception as e:
        logger.error(f"Failed to register KG schema tokens: {e}")


async def setup_kg(default_user: User | None = None):
    # Use environment variables if available (e.g. inside Docker)
    os.getenv("NEO4J_URI", "bolt://localhost:7687")
    os.getenv("NEO4J_USER", "neo4j")
    os.getenv("NEO4J_PASSWORD", "password")

    repo = KGRepository()
    await setup_indexes(repo)
    await setup_fulltext_indexes(repo)
    await setup_schema(repo)
    await repo.backfill_job_offer_properties()

    # Align Person id with authenticated API routes (``user_{postgres_id}``).
    if default_user is not None:
        person_id = f"user_{default_user.id}"
        person_name = default_user.full_name or "Default User"
        person_email = default_user.email
    else:
        person_id = "u1"
        person_name = "Default User"
        person_email = "user@example.com"

    logger.info(f"Setting up initial KG data for person {person_id}...")

    try:
        await repo.upsert_node(
            "Person",
            {"id": person_id, "name": person_name, "email": person_email},
        )
        logger.info("Successfully created/verified Person '%s'.", person_id)
    except Exception as e:
        logger.error(f"Failed to setup initial KG data: {e}")


if __name__ == "__main__":

    async def main():
        default_user = await setup_postgres()
        await setup_kg(default_user)

    asyncio.run(main())
