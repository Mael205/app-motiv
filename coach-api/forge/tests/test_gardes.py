"""Tests des gardes (SPEC §11.10).

Trois choses sont verrouillées ici, et ce sont les trois qui font la différence
entre un outil utile et un générateur de honte :

* **aucune garde ne peut viser zéro** — la contrainte est portée par le modèle,
  pas seulement par l'interface ;
* **le cumul de jours tenus ne redescend jamais**, même après un dépassement ;
* **le message d'un dépassement ne juge pas** — pas de vocabulaire de volonté,
  de rechute ou de discipline.
"""

from datetime import date, timedelta

import pytest

from forge.rules.gardes import Garde, held_days, held_weeks, message_for, week_state

LUNDI = date(2026, 3, 2)


def jours(*offsets: int, start: date = LUNDI) -> list[date]:
    return [start + timedelta(days=o) for o in offsets]


RESEAUX = Garde(key="reseaux", name="Réseaux sociaux", weekly_budget=2)
PORNO = Garde(key="porno", name="Porno", weekly_budget=1)


class TestBudgetJamaisZero:
    def test_une_garde_a_zero_est_refusee(self):
        with pytest.raises(ValueError, match="viser zéro"):
            Garde(key="x", name="Impossible", weekly_budget=0)

    def test_un_budget_a_un_est_accepte(self):
        assert Garde(key="x", name="Rare", weekly_budget=1).weekly_budget == 1


class TestSemaine:
    def test_sous_le_budget_la_semaine_tient(self):
        semaine = week_state(RESEAUX, jours(0, 3), LUNDI)
        assert semaine.marked == 2 and semaine.held
        assert semaine.left == 0
        assert semaine.label == "2 / 2"

    def test_au_dela_du_budget_la_semaine_ne_tient_pas(self):
        semaine = week_state(RESEAUX, jours(0, 1, 2), LUNDI)
        assert not semaine.held

    def test_zero_jour_marque_tient_evidemment(self):
        semaine = week_state(PORNO, [], LUNDI)
        assert semaine.held and semaine.left == 1

    def test_les_jours_d_une_autre_semaine_ne_comptent_pas(self):
        semaine = week_state(PORNO, jours(-3, -2), LUNDI)
        assert semaine.marked == 0


class TestCompteursMonotones:
    def test_jours_tenus_comptent_les_journees_declarees_sans_marque(self):
        declares = jours(0, 1, 2, 3, 4)
        marques = jours(1)
        assert held_days(declares, marques) == 4

    def test_une_journee_non_declaree_ne_compte_nulle_part(self):
        # Déclarés lundi et mardi seulement : mercredi n'est ni tenu ni marqué.
        assert held_days(jours(0, 1), []) == 2

    def test_un_depassement_ne_retire_aucun_jour_tenu(self):
        declares = jours(*range(14))
        avant = held_days(declares[:7], [])
        apres = held_days(declares, jours(7, 8, 9, 10))
        assert avant == 7
        assert apres >= avant, "le cumul de jours tenus ne redescend jamais"

    def test_semaines_tenues_comptent_les_semaines_sous_budget(self):
        declares = jours(*range(14))
        marques = jours(0, 1) + jours(7, 8, 9)   # semaine 1 tenue, semaine 2 non
        assert held_weeks(RESEAUX, declares, marques) == 1

    def test_semaine_sans_declaration_n_est_pas_comptee(self):
        assert held_weeks(RESEAUX, [], []) == 0


class TestTon:
    """Le §11.10 fait du ton une règle, pas une préférence."""

    INTERDITS = (
        "rechute",
        "volonté",
        "discipline",
        "échec",
        "bravo",
        "attention",
        "perdu",
        "encore",
    )

    def test_aucun_jugement_dans_un_depassement(self):
        semaine = week_state(RESEAUX, jours(0, 1, 2), LUNDI)
        texte = message_for(semaine, total_held_days=47).lower()
        for mot in self.INTERDITS:
            assert mot not in texte, f"« {mot} » n'a rien à faire dans un message de dépassement"

    def test_le_depassement_rappelle_ce_qui_reste_acquis(self):
        semaine = week_state(RESEAUX, jours(0, 1, 2), LUNDI)
        texte = message_for(semaine, total_held_days=47)
        assert "47" in texte and "acquis" in texte

    def test_une_semaine_sous_budget_est_annoncee_comme_tenue(self):
        semaine = week_state(RESEAUX, jours(0), LUNDI)
        assert "tient" in message_for(semaine, total_held_days=10)


@pytest.mark.django_db
class TestServiceEtConfidentialite:
    @pytest.fixture
    def garde(self, django_user_model):
        from forge.models import Garde as GardeModel, Profile

        user = django_user_model.objects.create_user(username="arthur", password="coach")
        Profile.objects.create(user=user)
        return GardeModel.objects.create(user=user, name="Réseaux sociaux", weekly_budget=2)

    def test_declarer_une_journee_tenue(self, garde):
        from forge import services

        panel = services.declare_garde(garde, day=LUNDI, occurred=False)
        ligne = panel["gardes"][0]
        assert ligne["declared_today"] and not ligne["occurred_today"]
        assert ligne["held_days"] == 1

    def test_redeclarer_corrige_au_lieu_d_empiler(self, garde):
        from forge import services
        from forge.models import GardeDay

        services.declare_garde(garde, day=LUNDI, occurred=False)
        panel = services.declare_garde(garde, day=LUNDI, occurred=True)
        assert GardeDay.objects.filter(garde=garde).count() == 1
        assert panel["gardes"][0]["occurred_today"]
        assert panel["gardes"][0]["held_days"] == 0

    def test_le_budget_zero_est_refuse_par_la_base(self, garde):
        from django.db.utils import IntegrityError
        from forge.models import Garde as GardeModel

        with pytest.raises(IntegrityError):
            GardeModel.objects.create(user=garde.user, name="Impossible", weekly_budget=0)

    def test_une_garde_ne_touche_ni_streak_ni_xp(self, garde):
        from forge import services
        from forge.models import DayStatus, Session

        services.declare_garde(garde, day=LUNDI, occurred=True)
        assert not Session.objects.filter(user=garde.user).exists()
        assert not DayStatus.objects.filter(user=garde.user).exists()

    def test_les_gardes_ne_sortent_pas_dans_le_bilan_de_l_ami(self, garde):
        """Le §11.10 l'interdit sans paramètre possible."""
        import inspect

        from forge import notifications

        source = inspect.getsource(notifications)
        assert "garde" not in source.lower(), (
            "aucune référence aux gardes ne doit exister dans le module qui construit "
            "les messages sortants"
        )
