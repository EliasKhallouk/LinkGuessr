from app.clues import HOLE, best_snippet, clues, mask, relation_sentence
from app.text import whole_words


def test_mask_full_name_is_one_hole():
    assert mask("Il est entraîné par Zinédine Zidane au Real.", "Zinédine Zidane") == f"Il est entraîné par {HOLE} au Real."


def test_mask_surname_alone_and_case():
    assert mask("ZIDANE marque ; plus tard Zidane entraîne.", "Zinédine Zidane") == f"{HOLE} marque ; plus tard {HOLE} entraîne."


def test_mask_keeps_particles_and_words_inside_others():
    text = "Louis de Funès joue avec Bourvil ; Louisiane n'est pas masquée."
    assert mask(text, "Louis de Funès") == f"{HOLE} joue avec Bourvil ; Louisiane n'est pas masquée."


def test_mask_ignores_disambiguation():
    assert mask("Prince chante.", "Prince (musicien)") == f"{HOLE} chante."


def test_relation_sentence_both_directions():
    answer, other = {"id": 1, "name": "Jacques"}, {"id": 2, "name": "Paul"}
    assert relation_sentence({"source_id": 1, "label": "élève de"}, answer, other) == f"{HOLE} est élève de Paul"
    assert relation_sentence({"source_id": 2, "label": "père"}, answer, other) == f"{HOLE} est père de Paul"


def test_clues_one_per_hidden_link():
    answer = {"id": 1, "qid": "Q1", "name": "Zinédine Zidane"}
    persons = {"Q2": {"id": 2, "qid": "Q2", "name": "Karim Benzema"}}
    hops = {"Q1-Q2": {"relations": [], "text": [
        {"source_id": 2, "target_id": 1, "in_lead": False, "mentions": 1, "snippet": "Benzema a toujours dit admirer Zidane depuis son enfance."}]}}
    assert clues(hops, answer, persons) == [{"with": "Q2", "relation": None, "snippet": f"Benzema a toujours dit admirer {HOLE} depuis son enfance."}]


def test_snippet_filters_junk_and_unrelated():
    answer = {"id": 1, "qid": "Q1", "name": "Fidel Castro"}
    other = {"id": 2, "qid": "Q2", "name": "Gérard Depardieu"}
    texts = [
        {"in_lead": True, "mentions": 3, "snippet": "ef name=date> (1769-1821), les grandes dates de Fidel Castro et autres"},
        {"in_lead": True, "mentions": 2, "snippet": "L'URSS a également ses têtes brûlées qui veulent changer le socialisme."},
        {"in_lead": False, "mentions": 1, "snippet": "Il se dit l'ami de Fidel Castro qu'il a rencontré en 1992."},
    ]
    assert best_snippet(texts, answer, other) == f"Il se dit l'ami de {HOLE} qu'il a rencontré en 1992."


def test_whole_words_cut_inside_a_word():
    assert whole_words("n, il rejoint le Paris Saint-Germain où il remporte le championnat avec Mbap") \
        == "il rejoint le Paris Saint-Germain où il remporte le championnat avec"


def test_whole_words_keeps_full_sentences():
    text = "En 2017, il rejoint le Paris Saint-Germain."
    assert whole_words(text) == text
    assert whole_words("« Il est le meilleur », dit-il.") == "« Il est le meilleur », dit-il."
