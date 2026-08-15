"""Tests du streak et des boucliers.

C'est l'endroit où un bug détruirait la confiance dans le système : chaque
règle du SPEC §4.2 a son test, y compris les cas tordus (jour neutre entre
deux ratés, reprise après décrochage).
"""

from datetime import date, timedelta

from forge.rules.streak import (
    Day,
    DayState,
    MAX_SHIELDS,
    evaluate,
    message_for,
)

D0 = date(2026, 3, 2)  # un lundi


def days(pattern: str, start: date = D0) -> list[Day]:
    """Construit un historique depuis une chaîne : V = validée, R = ratée, N = neutre."""
    mapping = {"V": DayState.VALIDEE, "R": DayState.RATEE, "N": DayState.NEUTRE}
    return [Day(start + timedelta(days=i), mapping[c]) for i, c in enumerate(pattern)]


class TestStreakDeBase:
    def test_journees_validees_incrementent(self):
        assert evaluate(days("VVV")).current == 3

    def test_historique_vide(self):
        state = evaluate([])
        assert state.current == 0 and state.shields == 2

    def test_meilleur_streak_retenu_meme_apres_cassure(self):
        state = evaluate(days("VVVVRRV"))
        assert state.best == 4
        assert state.current == 1


class TestBoucliers:
    def test_un_jour_rate_consomme_un_bouclier_et_le_streak_continue(self):
        state = evaluate(days("VVVRV"))
        assert state.current == 4          # les 3 + le dernier V, le raté n'a rien coupé
        assert state.shields == 1

    def test_sans_bouclier_un_seul_jour_rate_casse_le_streak(self):
        state = evaluate(days("VVVR"), starting_shields=0)
        assert state.current == 0
        assert state.broken_at == D0 + timedelta(days=3)

    def test_deux_jours_rates_cassent_meme_avec_des_boucliers(self):
        state = evaluate(days("VVVRR"), starting_shields=3)
        assert state.current == 0, "règle « jamais deux fois d'affilée »"
        assert state.shields == 2, "le second raté ne consomme pas de bouclier en plus"

    def test_un_bouclier_gagne_tous_les_cinq_jours(self):
        state = evaluate(days("VVVVV"), starting_shields=0)
        assert state.shields == 1
        assert state.consecutive_for_shield == 0

    def test_stock_de_boucliers_plafonne(self):
        state = evaluate(days("V" * 30), starting_shields=MAX_SHIELDS)
        assert state.shields == MAX_SHIELDS


class TestJoursNeutres:
    def test_un_jour_neutre_ne_casse_rien_et_ne_consomme_rien(self):
        state = evaluate(days("VVVNV"))
        assert state.current == 4
        assert state.shields == 2

    def test_deux_jours_neutres_consecutifs_sont_sans_effet(self):
        state = evaluate(days("VVVNNV"))
        assert state.current == 4
        assert state.shields == 2

    def test_un_jour_neutre_remet_a_zero_la_progression_vers_le_bouclier(self):
        # 4 jours validés, un jour off, un cinquième validé : pas de bouclier,
        # la série a été interrompue (SPEC §11.5).
        state = evaluate(days("VVVVNV"), starting_shields=0)
        assert state.shields == 0
        assert state.consecutive_for_shield == 1

    def test_un_neutre_entre_deux_rates_ne_protege_pas(self):
        # Les neutres sont retirés du calcul : R N R reste deux ratés d'affilée.
        state = evaluate(days("VVVRNR"), starting_shields=3)
        assert state.current == 0


class TestSanctionsEtReprise:
    def test_niveau_de_sanction_suit_la_serie_de_rates(self):
        assert evaluate(days("VVV")).sanction_level == 0
        assert evaluate(days("VVVR")).sanction_level == 1
        assert evaluate(days("VVVRR")).sanction_level == 2
        assert evaluate(days("VVVRRRRR")).sanction_level == 3

    def test_dette_de_dix_minutes_au_palier_deux_uniquement(self):
        assert evaluate(days("VVVR")).required_minutes == 25
        assert evaluate(days("VVVRR")).required_minutes == 35
        assert evaluate(days("VVVRRR")).required_minutes == 25, "jamais cumulable"

    def test_la_reprise_apres_trois_rates_rend_un_bouclier(self):
        state = evaluate(days("VVVRRRV"), starting_shields=1)
        # 1 au départ, −1 au premier raté, +1 au retour.
        assert state.shields == 1
        assert any(e.kind == "retour" for e in state.events)
        assert state.current == 1

    def test_message_apres_un_jour_rate_ne_culpabilise_pas(self):
        state = evaluate(days("VVVR"))
        message = message_for(state)
        assert "Bouclier consommé" in message
        assert "jamais deux fois" in message


class TestScenariosReels:
    def test_la_mauvaise_soiree_ne_casse_rien(self):
        """SPEC §15 : rater un mardi puis valider le mercredi doit tenir."""
        state = evaluate(days("VVRV"))
        assert state.current == 3
        assert state.shields == 1

    def test_le_retour_apres_decrochage_de_quatre_jours(self):
        """SPEC §15 : reprendre doit rapporter, pas punir davantage."""
        state = evaluate(days("VVVVVRRRRV"))
        assert state.current == 1
        assert state.sanction_level == 0
        assert any(e.kind == "retour" for e in state.events)

    def test_un_mois_en_dents_de_scie_reste_lisible(self):
        # 15 jours : 12 validés, 2 ratés isolés (absorbés par les boucliers),
        # 1 jour off. Un jour couvert par un bouclier n'incrémente pas le
        # streak mais ne le coupe pas : le compteur suit les jours travaillés.
        state = evaluate(days("VVVRVVNVVRVVVVV"))
        assert state.current == 12
        assert state.shields == 1, "2 consommés, 1 regagné par la série finale"
        assert state.broken_at is None, "aucun double raté, donc aucune cassure"
