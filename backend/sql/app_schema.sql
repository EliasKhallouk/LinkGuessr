-- Données de l'application (scores, requêtes, parties). Jamais touchées par les imports du pipeline.
-- Exécuté au démarrage de l'API : idempotent. Aucune adresse IP n'est stockée.
CREATE SCHEMA IF NOT EXISTS app;

CREATE TABLE IF NOT EXISTS app.score (
    id          bigserial PRIMARY KEY,
    game        text NOT NULL,
    name        text NOT NULL,
    score       integer NOT NULL,
    duration    integer NOT NULL,             -- secondes
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS score_rank_idx ON app.score (game, score DESC, duration, created_at DESC);

-- Paires demandées dans l'explorateur de chemins (a_qid < b_qid).
CREATE TABLE IF NOT EXISTS app.path_request (
    id          bigserial PRIMARY KEY,
    a_qid       text NOT NULL,
    b_qid       text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS path_request_time_idx ON app.path_request (created_at);

-- Une ligne par manche jouée : sert à mesurer la difficulté réelle et au Lab (humain vs réalité).
CREATE TABLE IF NOT EXISTS app.game_event (
    id           bigserial PRIMARY KEY,
    game         text NOT NULL,
    session      text,                        -- identifiant aléatoire généré par le navigateur
    payload      jsonb NOT NULL,
    data_version text,                        -- date du dump Wikipédia utilisé
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS game_event_game_idx ON app.game_event (game, created_at);
