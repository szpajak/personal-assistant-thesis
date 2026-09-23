CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT project_id IF NOT EXISTS FOR (p:Project) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT skill_id IF NOT EXISTS FOR (s:Skill) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT job_offer_id IF NOT EXISTS FOR (j:JobOffer) REQUIRE j.id IS UNIQUE;
CREATE CONSTRAINT job_offer_url IF NOT EXISTS FOR (j:JobOffer) REQUIRE j.url IS UNIQUE;
CREATE CONSTRAINT company_id IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT application_id IF NOT EXISTS FOR (a:Application) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT email_id IF NOT EXISTS FOR (e:Email) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT learning_resource_id IF NOT EXISTS FOR (lr:LearningResource) REQUIRE lr.id IS UNIQUE;
CREATE CONSTRAINT certificate_id IF NOT EXISTS FOR (c:Certificate) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT employment_id IF NOT EXISTS FOR (e:Employment) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT education_id IF NOT EXISTS FOR (e:Education) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT target_role_id IF NOT EXISTS FOR (t:TargetRole) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT skill_demand_snapshot_id IF NOT EXISTS FOR (d:SkillDemandSnapshot) REQUIRE d.id IS UNIQUE;

CREATE INDEX project_text_index IF NOT EXISTS FOR (n:Project) ON (n.title, n.description);
CREATE INDEX skill_text_index IF NOT EXISTS FOR (n:Skill) ON (n.name, n.category);
CREATE INDEX job_offer_text_index IF NOT EXISTS FOR (n:JobOffer) ON (n.title, n.description);

// Lucene full-text indexes power the lexical half of GraphRAG's hybrid
// (vector + full-text, fused via RRF - see backend/app/kg/graphrag.py).
// Kept separate from the plain b-tree indexes above, which only support
// equality/range lookups, not relevance-scored text search.
//
// NOTE: this file is documentation only - Neo4j does NOT auto-execute it.
// docker-compose mounts it at /docker-entrypoint-initdb.d/, a PostgreSQL
// convention Neo4j ignores. The indexes below are actually created by
// setup_fulltext_indexes() in backend/setup_kg.py, which entrypoint.sh runs
// on container startup when RUN_MIGRATIONS=true.
CREATE FULLTEXT INDEX project_fulltext_index IF NOT EXISTS FOR (n:Project) ON EACH [n.title, n.description];
CREATE FULLTEXT INDEX skill_fulltext_index IF NOT EXISTS FOR (n:Skill) ON EACH [n.name, n.category];
CREATE FULLTEXT INDEX joboffer_fulltext_index IF NOT EXISTS FOR (n:JobOffer) ON EACH [n.title, n.description];
CREATE FULLTEXT INDEX certificate_fulltext_index IF NOT EXISTS FOR (n:Certificate) ON EACH [n.title, n.issuer];
