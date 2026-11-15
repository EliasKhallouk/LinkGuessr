import math

import numpy as np
import pytest

from linkguessr_lab.typing.accord import alpha_masi, confusions, kappa, masi
from linkguessr_lab.typing.dataset import mark, split_items, variants
from linkguessr_lab.typing.grille import LABELS
from linkguessr_lab.typing.scores import score


# --- Noms ---

def test_variantes_du_nom():
    assert variants("Pierre Curie") == ["Pierre Curie", "Curie"]
    assert variants("Louis XIV") == ["Louis XIV"]  # pas de numéro de règne seul
    assert variants("Jean Rey (homme politique)") == ["Jean Rey"]  # « Rey » trop court


def test_masquage_et_balisage():
    s = "Pierre Curie épouse Marie Curie en 1895."
    assert mark(s, "Pierre Curie", "Marie Curie", masque=True) == ("[A] épouse [B] en 1895.", True, True)
    assert mark(s, "Pierre Curie", "Marie Curie", masque=False)[0] == \
        "[A]Pierre Curie[/A] épouse [B]Marie Curie[/B] en 1895."


def test_nom_de_famille_commun_non_touche():
    # « Curie » seul pourrait être l'un ou l'autre : on le laisse.
    assert mark("Les Curie et Marie Curie.", "Pierre Curie", "Marie Curie", masque=True)[0] == "Les Curie et [B]."


def test_pas_de_remplacement_au_milieu_d_un_mot():
    assert mark("Les Durandal de Durand.", None, "Jean Durand", masque=True) == ("Les Durandal de [B].", False, True)


# --- Découpage ---

def item(ordre, a, b, accord=False):
    return {"ordre": ordre, "source_qid": a, "target_qid": b, "accord": accord}


def test_decoupage_par_groupe_et_test_isole():
    items = [item(0, "Q1", "Q2", accord=True), item(1, "Q2", "Q3"), item(2, "Q3", "Q4")] + \
            [item(i, f"Q{10 * i}", f"Q{10 * i + 1}") for i in range(3, 103)]
    split = split_items(items)
    assert split[0] == "test"
    assert split[1] == split[2] == "exclu"  # Q2 est dans le test, Q3 relie 1 et 2
    parts = list(split.values())
    assert 10 <= parts.count("val") <= 20 and parts.count("train") > 80
    assert split_items(items) == split  # reproductible


# --- Scores ---

def test_scores_a_la_main():
    vrai = [["couple"], ["couple", "collaboration"], ["famille"], ["source"]]
    pred = [["couple"], ["couple"], ["couple"], ["source"]]
    s = score(vrai, pred)
    couple = s["types"]["par_type"]["couple"]
    assert couple["precision"] == pytest.approx(2 / 3) and couple["rappel"] == 1.0  # 2 bons sur 3 cochés
    assert s["types"]["par_type"]["collaboration"]["f1"] == 0.0
    assert s["exact"] == 0.5
    # Familles : « famille » et « couple » sont toutes deux « Personnel » : la 3e phrase devient juste.
    assert s["familles"]["par_type"]["Personnel"]["f1"] == 1.0


def test_poids_du_tirage():
    vrai, pred = [["couple"], ["couple"]], [["couple"], []]
    assert score(vrai, pred)["types"]["par_type"]["couple"]["rappel"] == 0.5
    assert score(vrai, pred, weights=[3, 1])["types"]["par_type"]["couple"]["rappel"] == 0.75


def test_cotoyes():
    s = score([["couple"]] * 3, [["couple"]] * 3, ["oui", "non", "oui"], ["oui", "oui", None])
    assert s["cotoyes"]["exactitude"] == pytest.approx(1 / 3)


# --- Accord ---

def test_kappa():
    a = np.array([1, 1, 0, 0])
    assert kappa(a, a) == 1.0
    assert kappa(a, 1 - a) == -1.0
    assert math.isnan(kappa(np.zeros(4), np.zeros(4)))  # jamais coché : non défini


def test_masi():
    f = frozenset
    assert masi(f({"couple"}), f({"couple"})) == 1.0
    assert masi(f({"couple"}), f({"couple", "collaboration"})) == pytest.approx(0.5 * 2 / 3)
    assert masi(f({"couple"}), f({"source"})) == 0.0


def test_alpha_masi():
    sets = [frozenset({l}) for l in LABELS[:5]] * 4
    assert alpha_masi(sets, sets) == 1.0
    assert alpha_masi(sets, sets[1:] + sets[:1]) < 0  # toujours en désaccord : pire que le hasard


def test_confusions():
    c = confusions([["collaboration"], ["couple"]], [["co_mention"], ["couple", "famille"]])
    assert c[("collaboration", "co_mention")] == 1 and c[("∅", "famille")] == 1
