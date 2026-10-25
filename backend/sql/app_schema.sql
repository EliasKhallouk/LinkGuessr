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

-- Défi du jour : pré-calculé (instantané des fiches, indépendant des rechargements de données).
CREATE TABLE IF NOT EXISTS app.daily_challenge (
    day          date PRIMARY KEY,             -- jour à Paris
    number       integer NOT NULL UNIQUE,      -- #1, #2… (jours depuis le lancement)
    path         text[] NOT NULL,              -- QID du chemin, la réponse comprise
    masked_index smallint NOT NULL,
    answer       jsonb NOT NULL,               -- fiche résumée de la personne cachée
    persons      jsonb NOT NULL,               -- fiches résumées de tout le chemin
    hops         jsonb NOT NULL,               -- explication de chaque lien
    hints        jsonb NOT NULL,
    forced       boolean NOT NULL DEFAULT false,
    created_at   timestamptz NOT NULL DEFAULT now()
);

-- Une tentative par appareil (identifiant anonyme du navigateur) et par jour.
CREATE TABLE IF NOT EXISTS app.daily_attempt (
    day          date NOT NULL,
    device       text NOT NULL,
    guesses      text[] NOT NULL DEFAULT '{}',
    solved       boolean NOT NULL DEFAULT false,
    finished     boolean NOT NULL DEFAULT false,
    started_at   timestamptz NOT NULL DEFAULT now(),
    finished_at  timestamptz,
    PRIMARY KEY (day, device)
);

-- Pseudo facultatif pour le classement du défi du jour (unique par jour, insensible à la casse).
ALTER TABLE app.daily_attempt ADD COLUMN IF NOT EXISTS pseudo text;
CREATE UNIQUE INDEX IF NOT EXISTS daily_attempt_pseudo_idx ON app.daily_attempt (day, lower(pseudo)) WHERE pseudo IS NOT NULL;

-- Retours des joueurs (une question en fin de partie). Anonymes.
CREATE TABLE IF NOT EXISTS app.feedback (
    id          bigserial PRIMARY KEY,
    game        text NOT NULL,
    rating      smallint NOT NULL CHECK (rating IN (-1, 1)),   -- 👎 / 👍
    comment     text,
    src         text,
    session     text,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS feedback_time_idx ON app.feedback (created_at);
CREATE INDEX IF NOT EXISTS game_event_kind_idx ON app.game_event ((payload->>'event'), created_at);
