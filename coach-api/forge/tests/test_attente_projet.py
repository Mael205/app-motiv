"""Le projet en attente déclarée (ajout du 17 août 2026).

Le cas est banal et rien ne le couvrait : un projet bloqué par quelqu'un
d'autre — une réponse qu'on attend, une pièce qui n'arrive pas, un accès qu'on
ne t'a pas donné.

Deux choses se testent ici, et la seconde compte plus que la première. Que
l'attente fasse taire ce qu'elle doit taire, d'abord. Et surtout qu'elle **ne
libère pas le slot** : c'est ce qui la distingue du frigo, et si elle le
libérait, la déclarer coûterait une renégociation de slots — donc personne ne
la déclarerait, donc elle ne servirait à rien.
"""

from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model

from forge import detections, services
from forge.models import Commitment, DayWindow, Profile, Project, ProjectHold, Track
from forge.rules import holds as regles

LUNDI = date(2026, 3, 2)


class TestLesRegles:
    def test_jamais_retroactive(self):
        verdict = regles.verifier(
            debut=LUNDI - timedelta(days=1), fin=LUNDI + timedelta(days=5),
            aujourdhui=LUNDI, raison="SAV en cours",
        )
        assert not verdict.ok and "après coup" in verdict.raison

    def test_une_raison_est_exigee(self):
        """Un blocage extérieur se nomme toujours ; sinon ce n'en est pas un."""
        verdict = regles.verifier(
            debut=LUNDI, fin=LUNDI + timedelta(days=5), aujourdhui=LUNDI, raison="rien"
        )
        assert not verdict.ok and "cinq mots" in verdict.raison

    def test_deux_semaines_au_maximum(self):
        verdict = regles.verifier(
            debut=LUNDI, fin=LUNDI + timedelta(days=20), aujourdhui=LUNDI,
            raison="carte mère en réparation",
        )
        assert not verdict.ok and "frigo" in verdict.raison

    def test_trois_jours_minimum(self):
        verdict = regles.verifier(
            debut=LUNDI, fin=LUNDI + timedelta(days=1), aujourdhui=LUNDI,
            raison="carte mère en réparation",
        )
        assert not verdict.ok and "rythme" in verdict.raison

    def test_une_semaine_passe(self):
        assert regles.verifier(
            debut=LUNDI, fin=LUNDI + timedelta(days=6), aujourdhui=LUNDI,
            raison="j'attends l'accès au dépôt",
        ).ok

    def test_la_semaine_se_leve_a_partir_de_quatre_jours(self):
        assert not regles.leve_la_semaine(LUNDI, LUNDI + timedelta(days=2), lundi=LUNDI)
        assert regles.leve_la_semaine(LUNDI, LUNDI + timedelta(days=3), lundi=LUNDI)

    def test_une_attente_sur_une_autre_semaine_ne_leve_rien(self):
        suivante = LUNDI + timedelta(days=7)
        assert not regles.leve_la_semaine(suivante, suivante + timedelta(days=6), lundi=LUNDI)

    def test_le_message_relit_la_raison(self):
        texte = regles.message("Bot Smash", LUNDI + timedelta(days=6), "j'attends l'API")
        assert "j'attends l'API" in texte and "slot reste pris" in texte


@pytest.mark.django_db
class TestCeQueLAttenteFait:
    def test_elle_ne_libere_pas_le_slot(self, user):
        """Le point qui la distingue du frigo."""
        projet = Project.objects.get(user=user, name="Bot Smash")
        avant = services.taken_slots(user)
        attendre(user, projet)
        assert services.taken_slots(user) == avant

    def test_le_projet_n_est_plus_propose(self, user):
        projet = Project.objects.get(user=user, name="Bot Smash")
        Project.objects.filter(user=user).exclude(id=projet.id).delete()
        assert services.propose(user, today=LUNDI) is not None
        attendre(user, projet)
        assert services.propose(user, today=LUNDI) is None

    def test_la_detection_projet_mort_se_tait(self, user):
        projet = Project.objects.get(user=user, name="Bot Smash")
        vieillir(projet, LUNDI - timedelta(days=30))

        plus_tard = LUNDI + timedelta(days=3)
        assert _morts(user, plus_tard)
        attendre(user, projet)
        assert not _morts(user, plus_tard)

    def test_les_jours_d_attente_sortent_du_decompte_apres(self, user):
        """Sinon le projet est déclaré mort le lendemain de son déblocage,
        c'est-à-dire au seul moment où il redevient vivant."""
        projet = Project.objects.get(user=user, name="Bot Smash")
        vieillir(projet, LUNDI - timedelta(days=1))
        attendre(user, projet, jours=13)

        apres = LUNDI + timedelta(days=14)
        assert not _morts(user, apres)

    def test_la_semaine_couverte_ne_coute_pas_le_rang(self, user):
        """Ne pas pouvoir travailler n'est pas manquer de fiabilité.

        La semaine **sort du calcul**, elle n'y est pas créditée : elle ne
        compte que si les autres engagements, eux, ont été tenus. Un projet
        bloqué ne fait pas gagner une semaine, il cesse d'en faire perdre une.
        """
        bloque = Project.objects.get(user=user, name="Bot Smash")
        tenu = Project.objects.get(user=user, name="Bestiaire")
        Commitment.objects.create(
            project=bloque, week_start=LUNDI, planned_sessions=3, done_sessions=0
        )
        Commitment.objects.create(
            project=tenu, week_start=LUNDI, planned_sessions=3, done_sessions=3
        )
        suivant = LUNDI + timedelta(days=7)

        assert services.rank_state(user, today=suivant)["weeks_kept"] == 0
        attendre(user, bloque, jours=6)
        assert services.rank_state(user, today=suivant)["weeks_kept"] == 1

    def test_une_semaine_entierement_bloquee_ne_se_credite_pas(self, user):
        projet = Project.objects.get(user=user, name="Bot Smash")
        Commitment.objects.create(
            project=projet, week_start=LUNDI, planned_sessions=3, done_sessions=0
        )
        attendre(user, projet, jours=6)
        assert services.rank_state(user, today=LUNDI + timedelta(days=7))["weeks_kept"] == 0

    def test_on_en_sort_quand_on_veut_et_des_ce_soir(self, user):
        """Sortir à 19h pour découvrir que le projet reste absent de la soirée
        viderait la sortie de son sens."""
        projet = Project.objects.get(user=user, name="Bot Smash")
        attendre(user, projet)
        mardi = LUNDI + timedelta(days=1)
        assert services.end_hold(user, projet, today=mardi)
        assert services.projects_on_hold(user, day=mardi) == set()
        # Le lundi, lui, reste couvert : il a eu lieu sous l'attente.
        assert services.projects_on_hold(user, day=LUNDI) == {projet.id}

    def test_on_n_en_sort_pas_deux_fois(self, user):
        projet = Project.objects.get(user=user, name="Bot Smash")
        attendre(user, projet)
        assert services.end_hold(user, projet, today=LUNDI + timedelta(days=1))
        assert not services.end_hold(user, projet, today=LUNDI + timedelta(days=2))

    def test_deux_attentes_ne_se_superposent_pas(self, user):
        projet = Project.objects.get(user=user, name="Bot Smash")
        attendre(user, projet)
        with pytest.raises(ValueError):
            attendre(user, projet)


def vieillir(projet, jour: date) -> None:
    """Antidate la création d'un projet, pour que le décompte ait un passé."""
    projet.created_at = projet.created_at.replace(
        year=jour.year, month=jour.month, day=jour.day
    )
    projet.save(update_fields=["created_at"])


def attendre(user, projet, *, jours: int = 6) -> ProjectHold:
    return services.declare_hold(
        user,
        projet,
        starts_on=LUNDI,
        ends_on=LUNDI + timedelta(days=jours),
        reason="j'attends l'accès au dépôt",
        today=LUNDI,
    )


def _morts(user, jour: date) -> list:
    return [d for d in detections.toutes(user, today=jour) if d.kind == "projet_mort"]


@pytest.fixture
def user(db):
    User = get_user_model()
    user = User.objects.create_user(username="test", password="test")
    profile = Profile.objects.create(user=user)
    for weekday in range(7):
        DayWindow.objects.create(profile=profile, weekday=weekday)
    atelier = Track.objects.create(user=user, kind=Track.ATELIER)
    Project.objects.create(user=user, track=atelier, name="Bot Smash", slot=1)
    Project.objects.create(user=user, track=atelier, name="Bestiaire", slot=2)
    return user
