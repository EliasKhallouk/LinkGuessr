-- Créés après le chargement (bien plus rapide que d'indexer pendant les COPY).
-- pg_trgm est installée par infra/vm/setup_vm.sh (il faut être superutilisateur).

CREATE UNIQUE INDEX person_title_idx ON person (title);
CREATE INDEX person_search_trgm_idx ON person USING gin (search_text gin_trgm_ops);
CREATE INDEX person_search_prefix_idx ON person (search_text text_pattern_ops);  -- saisies de 1-2 lettres
CREATE INDEX person_popularity_idx ON person (popularity DESC);
CREATE INDEX person_domain_idx ON person (primary_domain);
CREATE INDEX person_birth_year_idx ON person (birth_year);

CREATE INDEX fact_person_idx ON fact (person_id, prop);
CREATE INDEX fact_value_idx ON fact (value_qid, prop);

CREATE INDEX text_link_target_idx ON text_link (target_id);
CREATE INDEX relation_source_idx ON relation (source_id);
CREATE INDEX relation_target_idx ON relation (target_id);
CREATE INDEX edge_b_idx ON edge (b);

ANALYZE;
