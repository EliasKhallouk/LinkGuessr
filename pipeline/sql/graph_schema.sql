-- Données Wikipédia/Wikidata, entièrement reconstruites à chaque import.
-- Le chargeur crée ces tables dans le schéma « staging », puis l'échange avec « graph ».

CREATE TABLE person (
    id              integer PRIMARY KEY,      -- index dense 0..N-1, utilisé par le graphe en mémoire de l'API
    qid             text NOT NULL UNIQUE,
    title           text NOT NULL,            -- titre frwiki (underscores)
    title_en        text,
    name            text NOT NULL,
    search_text     text NOT NULL,            -- nom, alias, pseudonymes : minuscules sans accents
    description     text,
    aliases         text[],
    birth_name      text,
    pseudonyms      text[],
    gender          text,
    birth_year      integer,
    birth_date      date,
    birth_precision smallint,                 -- précision Wikidata : 11 jour, 10 mois, 9 année, 8 décennie, 7 siècle
    death_year      integer,
    death_date      date,
    death_precision smallint,
    birth_place     text,                     -- QID → ref
    birth_country   text,
    death_place     text,
    death_country   text,
    citizenships    text[],
    occupations     text[],
    domains         text[],
    primary_domain  text,
    image           text,                     -- nom de fichier Wikimedia Commons
    height_cm       smallint,
    external_ids    jsonb,
    sitelinks       smallint,                 -- nombre d'éditions de Wikipédia qui ont un article
    article_len     integer,
    pageviews_12m   bigint,                   -- vues de l'article frwiki sur 12 mois (lecteurs humains)
    pageviews_monthly integer[],              -- les 12 mois, du plus ancien au plus récent
    infobox         text,
    categories      text[],
    lead            text,
    n_chars         integer,
    n_sections      smallint,
    -- Calculé par l'étape « graph »
    degree          integer,
    in_links        integer,
    out_links       integer,
    pagerank        real,
    community       integer,
    popularity      real                      -- score 0-1 (notoriété), pour difficulté et autocomplétion
);

-- Entités citées par les fiches : lieux, professions, partis, clubs, prix...
CREATE TABLE ref (
    qid         text PRIMARY KEY,
    label       text,
    description text,
    lat         double precision,
    lon         double precision,
    country_qid text,
    instance_of text[]
);

-- Faits datés : une ligne par affirmation Wikidata (fonction, club, prix, formation...).
CREATE TABLE fact (
    person_id   integer NOT NULL,
    prop        text NOT NULL,
    value_qid   text NOT NULL,
    start_year  integer,
    end_year    integer,
    start_date  date,
    end_date    date,
    preferred   boolean NOT NULL,
    qualifiers  jsonb
);

-- Lien textuel : l'article de source cite target dans son texte.
CREATE TABLE text_link (
    source_id   integer NOT NULL,
    target_id   integer NOT NULL,
    mentions    smallint NOT NULL,
    first_pos   real NOT NULL,              -- position de la 1re mention dans l'article (0 = début)
    in_lead     boolean NOT NULL,
    in_infobox  boolean NOT NULL,
    sections    text[],
    snippet     text,
    PRIMARY KEY (source_id, target_id)
);

-- Relation Wikidata typée entre deux personnes (famille, élève, succession...).
CREATE TABLE relation (
    source_id   integer NOT NULL,
    target_id   integer NOT NULL,
    prop        text NOT NULL,
    family      text NOT NULL,
    label       text NOT NULL,
    context_qid text,                       -- ex. la fonction pour une succession
    start_year  integer,
    end_year    integer
);

-- Graphe non orienté utilisé par les jeux (a < b). Chargé en mémoire par l'API.
CREATE TABLE edge (
    a           integer NOT NULL,
    b           integer NOT NULL,
    kinds       smallint NOT NULL,          -- bits : 1 texte a→b, 2 texte b→a, 4 relation Wikidata
    mentions    smallint NOT NULL,
    weight      real NOT NULL,              -- force du lien (plus haut = plus fort)
    PRIMARY KEY (a, b)
);
