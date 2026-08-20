"""Habitudes horaires et choses à faire une fois.

Deux ajouts qui touchent au point le plus sensible du système : ce qui compte
et ce qui ne compte pas. Les tests d'ici gardent surtout des **absences** —
qu'un ponctuel ne rapporte rien, qu'il n'entre pas dans la décision du soir,
qu'une coche hors fenêtre ne crédite pas. Ce sont ces règles-là qui se perdent
au premier refactoring, parce que les enlever ne casse aucun écran.
"""

from datetime import date, time, timedelta

import pytest

from forge.rules import routines as rules


class TestFenetreHoraire:
    """« Se lever tôt » n'a de sens que si l'heure de la coche décide."""

    LEVER = rules.Routine(
        key="1", name="Debout", weekly_target=6, deadline=time(7, 30), anchor=rules.REVEIL
    )
    COUCHER = rules.Routine(
        key="2", name="Au lit", weekly_target=6, deadline=time(23, 30), anchor=rules.AVANT_COUCHER
    )

    def test_avant_l_heure_passe(self):
        assert rules.within_window(self.LEVER, time(7, 10))

    def test_apres_l_heure_ne_passe_pas(self):
        assert not rules.within_window(self.LEVER, time(9, 0))

    def test_pile_a_l_heure_passe(self):
        # La borne est inclusive : refuser 7h30 pour une limite à 7h30 est le
        # genre de détail qui fait perdre confiance dans le compteur.
        assert rules.within_window(self.LEVER, time(7, 30))

    def test_apres_minuit_est_tard_et_non_tot(self):
        # Le défaut que cette mécanique doit empêcher. Une coche « au lit » à
        # 00h20 appartient à la journée d'hier, qui bascule à 4h : comparer les
        # heures brutes la ferait passer pour un coucher à 00h20 < 23h30, donc
        # dans les temps. C'est exactement le mensonge à ne pas laisser passer.
        assert not rules.within_window(self.COUCHER, time(0, 20))
        assert rules.within_window(self.COUCHER, time(22, 45))

    def test_la_direction_inverse_se_lit_aussi(self):
        sport = rules.Routine(
            key="3", name="Rien après", weekly_target=5, deadline=time(21, 0), direction=rules.APRES
        )
        assert rules.within_window(sport, time(22, 0))
        assert not rules.within_window(sport, time(18, 0))

    def test_sans_fenetre_tout_moment_convient(self):
        libre = rules.Routine(key="4", name="Étirements", weekly_target=5)
        assert rules.within_window(libre, time(3, 59))
        assert rules.within_window(libre, time(15, 0))

    def test_le_libelle_se_lit_en_francais(self):
        assert rules.window_label(self.LEVER) == "avant 7h30"
        assert rules.window_label(rules.Routine(key="5", name="x", weekly_target=1)) == ""

    def test_une_bascule_de_journee_differente_est_respectee(self):
        # Quelqu'un qui bascule à 2h du matin n'a pas la même nuit, et 2h30 ne
        # tombe pas du même côté de la frontière selon le réglage : avec une
        # bascule à 2h, c'est le tout début d'une nouvelle journée, donc très en
        # avance sur un coucher à 23h30 ; avec la bascule à 4h par défaut, c'est
        # encore la nuit d'hier, donc trois heures trop tard. La règle lit le
        # réglage, elle ne suppose jamais 4h.
        assert rules.within_window(self.COUCHER, time(2, 30), rollover_hour=2)
        assert not rules.within_window(self.COUCHER, time(2, 30))


@pytest.mark.django_db
class TestCocheHorsFenetre:
    @pytest.fixture
    def routine(self, django_user_model):
        from forge.models import Profile, Routine, Track

        user = django_user_model.objects.create_user(username="arthur", password="coach")
        Profile.objects.create(user=user)
        piste, _ = Track.objects.get_or_create(user=user, kind=Track.ENTRETIEN)
        return Routine.objects.create(
            user=user, track=piste, name="Debout", weekly_target=6, deadline=time(7, 30)
        )

    def test_la_coche_a_l_heure_compte_et_paie(self, routine):
        from forge import services

        resultat = services.check_routine(routine, day=date(2026, 8, 19), at=time(7, 10))
        assert resultat["on_time"] and resultat["shards"] > 0
        assert resultat["week"]["done"] == 1

    def test_la_coche_en_retard_est_gardee_mais_ne_compte_pas(self, routine):
        # Gardée, parce que le §17 interdit d'effacer ce qui a eu lieu, et parce
        # qu'un bouton qui ne fait rien passe pour cassé. Sans effet, parce
        # qu'une habitude horaire dont l'heure ne décide de rien ne mesure rien.
        from forge import services
        from forge.models import RoutineCheck

        resultat = services.check_routine(routine, day=date(2026, 8, 19), at=time(10, 0))
        assert resultat["created"] and not resultat["on_time"]
        assert resultat["shards"] == 0
        assert resultat["week"]["done"] == 0
        assert RoutineCheck.objects.filter(routine=routine, on_time=False).count() == 1

    def test_une_coche_en_retard_ne_paie_aucun_eclat(self, routine):
        from forge import services
        from forge.models import Profile

        avant = Profile.objects.get(user=routine.user).shards
        services.check_routine(routine, day=date(2026, 8, 19), at=time(23, 0))
        assert Profile.objects.get(user=routine.user).shards == avant

    def test_le_panneau_montre_le_retard_plutot_qu_une_ligne_a_faire(self, routine):
        from forge import services

        jour = date(2026, 8, 19)
        services.check_routine(routine, day=jour, at=time(10, 0))
        panneau = services.routine_panel(routine.user, today=jour)
        ligne = panneau["groups"][0]["routines"][0]
        assert ligne["late_today"] is True
        assert ligne["checked"] is False
        assert ligne["window"] == "avant 7h30"

    def test_une_routine_sans_fenetre_ne_change_pas_de_comportement(self, django_user_model):
        # La garantie qui compte pour l'existant : ajouter la mécanique ne
        # modifie aucune des routines déjà là.
        from forge import services
        from forge.models import Profile, Routine, Track

        user = django_user_model.objects.create_user(username="autre", password="coach")
        Profile.objects.create(user=user)
        piste, _ = Track.objects.get_or_create(user=user, kind=Track.ENTRETIEN)
        libre = Routine.objects.create(user=user, track=piste, name="Étirements", weekly_target=5)

        resultat = services.check_routine(libre, day=date(2026, 8, 19), at=time(3, 0))
        assert resultat["on_time"] and resultat["shards"] > 0


@pytest.mark.django_db
class TestPonctuels:
    """Une course écrite quelque part sort de la tête sans prendre de valeur."""

    @pytest.fixture
    def user(self, django_user_model):
        from forge.models import Profile

        user = django_user_model.objects.create_user(username="arthur", password="coach")
        Profile.objects.create(user=user)
        return user

    @pytest.fixture
    def client(self, user):
        from rest_framework.test import APIClient

        c = APIClient()
        c.force_authenticate(user=user)
        return c

    def test_creer_et_cocher(self, client):
        cree = client.post("/api/ponctuels", {"label": "Commander la carte mère"}, format="json")
        assert cree.status_code == 201
        bascule = client.post(f"/api/ponctuels/{cree.data['id']}", format="json")
        assert bascule.data["done"] is True

    def test_le_retard_est_calcule_par_le_serveur(self, client, user):
        from django.utils import timezone

        from forge.rules.calendar import coach_day

        today = coach_day(timezone.now(), user.profile.timezone_name, 4)
        client.post(
            "/api/ponctuels",
            {"label": "Appeler le dentiste", "due_on": (today - timedelta(days=2)).isoformat()},
            format="json",
        )
        ligne = client.get("/api/ponctuels").data[0]
        assert ligne["late"] is True

    def test_un_ponctuel_ne_rapporte_ni_xp_ni_eclats(self, client, user):
        # La règle qui compte. Si cocher une course payait quoi que ce soit, la
        # soirée la plus rentable serait une soirée de courses — l'inverse
        # exact de ce que tout le reste du système protège (§0.2, §17).
        from forge.models import Profile, Session

        avant = Profile.objects.get(user=user).shards
        cree = client.post("/api/ponctuels", {"label": "Poster le colis"}, format="json")
        client.post(f"/api/ponctuels/{cree.data['id']}", format="json")

        assert Profile.objects.get(user=user).shards == avant
        assert not Session.objects.filter(user=user).exists()

    def test_un_ponctuel_n_apparait_pas_dans_l_accueil(self, client, user):
        # Le §11.1 : l'accueil porte une décision, pas un inventaire. Une liste
        # de courses à côté du bouton en ferait une option.
        client.post("/api/ponctuels", {"label": "Commander la carte mère"}, format="json")
        accueil = client.get("/api/home").data
        assert "ponctuels" not in accueil
        assert "carte mère" not in str(accueil)

    def test_les_datees_passent_devant(self, client, user):
        from django.utils import timezone

        from forge.rules.calendar import coach_day

        today = coach_day(timezone.now(), user.profile.timezone_name, 4)
        client.post("/api/ponctuels", {"label": "Sans date"}, format="json")
        client.post(
            "/api/ponctuels",
            {"label": "Avec date", "due_on": (today + timedelta(days=3)).isoformat()},
            format="json",
        )
        assert [i["label"] for i in client.get("/api/ponctuels").data] == ["Avec date", "Sans date"]


@pytest.mark.django_db
class TestCreerUneHabitudeHoraire:
    """Le trou trouvé en relisant : la mécanique existait, le geste non.

    Une routine ne se crée que par l'assistant, et son verbe ignorait la
    fenêtre horaire. « Debout avant 7h30 » était donc **incréable** — la règle
    tournait, les tests passaient, et personne n'aurait pu s'en servir. C'est le
    mode de défaillance le plus discret : rien n'échoue, la chose n'existe pas.
    """

    @pytest.fixture
    def user(self, django_user_model):
        from forge.models import Profile, Track

        user = django_user_model.objects.create_user(username="arthur", password="coach")
        Profile.objects.create(user=user)
        Track.objects.get_or_create(user=user, kind=Track.ENTRETIEN)
        return user

    def _appliquer(self, user, cle, params):
        from datetime import date as _date

        from forge.actions import resoudre

        plan = resoudre(user, cle, params, today=_date(2026, 8, 19))
        plan.appliquer()
        return plan

    def test_l_assistant_cree_une_habitude_avec_sa_fenetre(self, user):
        from forge.models import Routine

        self._appliquer(user, "routine.creer", {"nom": "Debout", "ancrage": "reveil", "heure": "07:30"})
        routine = Routine.objects.get(user=user, name="Debout")
        assert routine.deadline == time(7, 30)
        assert routine.direction == "avant"

    def test_les_trois_ecritures_d_heure_se_lisent(self, user):
        from forge.models import Routine

        for i, texte in enumerate(("7h30", "07:30", "7h")):
            self._appliquer(user, "routine.creer", {"nom": f"R{i}", "heure": texte})
        heures = [r.deadline for r in Routine.objects.filter(user=user).order_by("name")]
        assert heures == [time(7, 30), time(7, 30), time(7, 0)]

    def test_une_heure_illisible_est_refusee_avec_le_bon_format(self, user):
        from forge.actions import ActionRefusee

        with pytest.raises(ActionRefusee, match="07:30"):
            self._appliquer(user, "routine.creer", {"nom": "Debout", "heure": "tôt le matin"})

    def test_la_fenetre_se_retire(self, user):
        # Le retour en arrière doit exister : une heure posée par erreur sur une
        # routine de trois minutes la ferait rater pour un quart d'heure.
        from forge.models import Routine

        self._appliquer(user, "routine.creer", {"nom": "Debout", "heure": "07:30"})
        self._appliquer(user, "routine.regler", {"routine": "Debout", "heure": "aucune"})
        assert Routine.objects.get(user=user, name="Debout").deadline is None

    def test_le_plan_annonce_la_fenetre_avant_d_ecrire(self, user):
        # Le §5.6 veut un avant/après lisible : une fenêtre appliquée sans être
        # annoncée serait une écriture qu'on n'a pas vue venir.
        from datetime import date as _date

        from forge.actions import resoudre

        plan = resoudre(
            user, "routine.creer", {"nom": "Au lit", "heure": "23:30"}, today=_date(2026, 8, 19)
        )
        assert "avant 23h30" in plan.apres

    def test_le_catalogue_ne_gagne_aucun_verbe(self, user):
        # La fenêtre passe par les verbes existants. Un verbe de plus, c'est une
        # chose de plus à comprendre — et le §17 tient au catalogue fermé.
        from forge.rules.actions import CATALOGUE

        assert len(CATALOGUE) == 32
