"""Tests du regroupement des requêtes DNS en rafales.

    coach-api/.venv/Scripts/python -m pytest coach-agent

Une requête DNS est un événement, pas une durée. Le point surveillé ici est donc
qu'on ne fabrique jamais une mesure d'usage à partir d'un compte de requêtes :
on rend l'amplitude d'une rafale, et une requête isolée reste sous le seuil de
marquage du serveur — sinon un tracker embarqué marquerait une journée.
"""

from datetime import datetime, timedelta, timezone

from adguard import MIN_BURST_MINUTES, Burst, bursts, to_entries

BASE = datetime(2026, 3, 2, 21, 0, tzinfo=timezone.utc)


def at(minutes: float) -> datetime:
    return BASE + timedelta(minutes=minutes)


class TestRafales:
    def test_des_requetes_rapprochees_forment_une_seule_rafale(self):
        events = [(at(0), "reseaux"), (at(2), "reseaux"), (at(4), "reseaux")]
        found = bursts(events)
        assert len(found) == 1
        assert found[0].minutes == 4

    def test_un_trou_coupe_la_rafale(self):
        # 30 minutes de silence : rien ne prouve qu'il se passait quelque chose.
        events = [(at(0), "reseaux"), (at(2), "reseaux"), (at(32), "reseaux"), (at(34), "reseaux")]
        found = bursts(events)
        assert len(found) == 2
        assert [b.minutes for b in found] == [2, 2]

    def test_les_categories_sont_separees(self):
        events = [(at(0), "reseaux"), (at(1), "adulte"), (at(3), "reseaux")]
        found = bursts(events)
        assert {b.category for b in found} == {"reseaux", "adulte"}

    def test_les_rafales_sortent_dans_l_ordre_du_temps(self):
        events = [(at(20), "adulte"), (at(0), "reseaux")]
        found = bursts(events)
        assert [b.category for b in found] == ["reseaux", "adulte"]

    def test_l_ordre_d_arrivee_ne_change_rien(self):
        desordre = [(at(4), "reseaux"), (at(0), "reseaux"), (at(2), "reseaux")]
        assert bursts(desordre)[0].minutes == 4


class TestPasDeMesureInventee:
    """Une requête isolée ne doit jamais suffire à marquer une journée."""

    def test_une_requete_seule_reste_sous_le_seuil_du_serveur(self):
        found = bursts([(at(0), "adulte")])
        assert found[0].minutes == MIN_BURST_MINUTES
        # Le serveur marque à partir de 3 minutes (MIN_MINUTES_TO_MARK).
        assert found[0].minutes < 3, "un tracker embarqué ne doit pas marquer une journée"

    def test_deux_requetes_tres_proches_restent_sous_le_seuil(self):
        found = bursts([(at(0), "adulte"), (at(0.5), "adulte")])
        assert found[0].minutes < 3

    def test_une_vraie_session_depasse_le_seuil(self):
        events = [(at(i), "adulte") for i in range(0, 13, 2)]
        assert bursts(events)[0].minutes == 12


class TestEntrees:
    def test_chaque_rafale_porte_sa_fenetre(self):
        entries = to_entries([Burst(category="reseaux", start=at(0), end=at(10))])
        assert entries[0]["category"] == "reseaux"
        assert entries[0]["minutes"] == 10
        assert entries[0]["started_at"] == at(0).isoformat()
        assert entries[0]["ended_at"] == at(10).isoformat()

    def test_aucune_entree_ne_transporte_de_domaine(self):
        entries = to_entries([Burst(category="adulte", start=at(0), end=at(9))])
        assert set(entries[0]) == {"category", "minutes", "started_at", "ended_at"}
