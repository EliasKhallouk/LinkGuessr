from app.clues import HOLE, clues, mask, relation_sentence


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
        {"source_id": 2, "target_id": 1, "in_lead": False, "mentions": 1, "snippet": "Benzema admire Zidane."}]}}
    assert clues(hops, answer, persons) == [{"with": "Q2", "relation": None, "snippet": f"Benzema admire {HOLE}."}]
