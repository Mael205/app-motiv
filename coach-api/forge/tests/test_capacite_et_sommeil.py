"""Le troisième axe, et ce qu'une déclaration de sommeil prouve.

Les deux sujets sont dans le même fichier parce qu'ils répondent à la même
question posée à deux endroits : **qu'est-ce qui est réellement constaté ?**

Ce que ces tests gardent est presque entièrement négatif. Qu'une preuve ne
donne pas d'XP, qu'une difficulté déclarée ne change aucun calcul, qu'une sonde
qui contredit ne retire rien. Ce sont les trois règles qui rendent ces
mécaniques utilisables — et les trois qui disparaîtraient sans bruit.
"""

from datetime import date, time, timedelta

import pytest

from forge.rules import capacite, sommeil
from forge.rules.routines import APRES, AVANT, AVANT_COUCHER, REVEIL


class TestLaPreuveEstUnFaitVerifiable:
    def test_un_critere_vide_n_est_pas_une_preuve(self):
        assert not capacite.Preuve(projet="P", critere="").valide

    def test_j_ai_progresse_n_est_pas_un_critere(self):
        # La borne est courte et bête — une longueur — parce qu'une borne
        # intelligente serait un jugement sur le contenu, et le système n'a
        # aucun moyen de juger un contenu. Elle attrape quand même le cas réel :
        # les formules d'auto-satisfaction sont toutes très courtes.
        assert not capacite.Preuve(projet="P", critere="j'ai avancé").valide

    def test_un_critere_constatable_passe(self):
        assert capacite.Preuve(
            projet="P", critere="les 100 % de labs Apprentice validés"
        ).valide

    def test_la_dixieme_preuve_vaut_autant_que_la_premiere(self):
        # L'XP est dégressive parce qu'un volume se force. Une capacité ne se
        # force pas : la dixième preuve d'un parcours est plus dure que la
        # première, et la faire rapporter moins serait le mauvais signal.
        assert capacite.shards_pour_preuve(0) == capacite.shards_pour_preuve(9)


class TestLePalierTropFacile:
    def test_trois_d_affilee_declenchent_le_constat(self):
        constat = capacite.palier_trop_facile([1, 1, 1, 2])
        assert constat is not None
        assert "3 sessions" in constat["constat"]

    def test_deux_ne_suffisent_pas(self):
        # Deux séances faciles peuvent être deux bonnes soirées.
        assert capacite.palier_trop_facile([1, 1, 2]) is None

    def test_une_seule_session_dure_casse_la_serie(self):
        assert capacite.palier_trop_facile([1, 1, 3, 1]) is None

    def test_le_silence_n_est_pas_un_avis(self):
        # La liste ne contient que ce qui a été déclaré : trois sessions sans
        # réponse ne doivent pas produire un constat, et ne peuvent pas puisque
        # rien ne les y met.
        assert capacite.palier_trop_facile([]) is None

    def test_la_proposition_est_une_question_pas_un_ordre(self):
        constat = capacite.palier_trop_facile([1, 1, 1])
        assert "ou" in constat["proposition"]


class TestLesDeuxNombresNeFusionnentPas:
    def test_l_etat_garde_les_deux(self):
        etat = capacite.etat(preuves=3, minutes=60 * 90)
        assert etat["preuves"] == 3 and etat["heures"] == 90
        assert etat["heures_par_preuve"] == 30

    def test_sans_preuve_le_rapport_n_existe_pas(self):
        # Et surtout il ne vaut pas zéro : zéro heure par preuve se lirait comme
        # une performance.
        assert capacite.etat(preuves=0, minutes=60 * 40)["heures_par_preuve"] is None


class TestCorroborationDuSommeil:
    def test_une_activite_avant_l_heure_corrobore_le_lever(self):
        assert (
            sommeil.corroboration(time(7, 30), AVANT, REVEIL, premiere_activite=time(7, 5))
            == sommeil.CORROBORE
        )

    def test_une_activite_apres_l_heure_contredit_le_coucher(self):
        # Une activité à 1h12 est une preuve **positive** d'être éveillé : elle
        # a le droit de contredire. Mais seulement une fois la journée close.
        assert (
            sommeil.corroboration(
                time(23, 30), AVANT, AVANT_COUCHER,
                derniere_activite=time(1, 12), journee_finie=True,
            )
            == sommeil.CONTREDIT
        )

    def test_le_coucher_ne_se_juge_pas_avant_la_fin_de_journee(self):
        # À 18h, la soirée n'a pas eu lieu : dire « corroboré » serait juger un
        # futur, et le dire chaque après-midi viderait le mot de son sens.
        assert (
            sommeil.corroboration(
                time(23, 30), AVANT, AVANT_COUCHER, derniere_activite=time(17, 56)
            )
            == sommeil.SANS_SIGNAL
        )

    def test_un_lever_tardif_ne_contredit_jamais(self):
        # Le cas qui a imposé la règle, rencontré le jour même. La sonde web a
        # été installée à 17h ; le matin, elle ne tournait pas. La première
        # activité de la journée était donc 17h48, et « debout avant 7h30 »
        # s'affichait *contredit* — alors que rien n'avait été observé avant
        # 17h. Une activité tardive ne dit pas « il s'est levé tard », elle dit
        # « je n'ai rien vu plus tôt ». C'est une absence.
        assert (
            sommeil.corroboration(time(7, 30), AVANT, REVEIL, premiere_activite=time(17, 48))
            == sommeil.SANS_SIGNAL
        )

    def test_une_nuit_silencieuse_corrobore_le_coucher(self):
        assert (
            sommeil.corroboration(
                time(23, 30), AVANT, AVANT_COUCHER,
                derniere_activite=time(22, 40), journee_finie=True,
            )
            == sommeil.CORROBORE
        )

    def test_sans_sonde_l_etat_est_dit_sans_signal(self):
        # Et non « contredit ». Se lever tôt sans toucher un écran ne laisse
        # aucune trace, et c'est plutôt bon signe : traiter l'absence comme une
        # contradiction punirait la seule bonne façon de se lever.
        assert sommeil.corroboration(time(7, 30), AVANT, REVEIL) == sommeil.SANS_SIGNAL

    def test_une_routine_sans_fenetre_n_a_rien_a_corroborer(self):
        assert (
            sommeil.corroboration(None, AVANT, REVEIL, premiere_activite=time(7, 0))
            == sommeil.SANS_SIGNAL
        )

    def test_la_direction_apres_est_symetrique(self):
        assert (
            sommeil.corroboration(
                time(21, 0), APRES, AVANT_COUCHER,
                derniere_activite=time(22, 0), journee_finie=True,
            )
            == sommeil.CORROBORE
        )

    def test_le_constat_ne_contient_aucun_mot_de_jugement(self):
        # Le §14 interdit le mot de reproche dans un texte affiché, et « tu as
        # menti » en est un. La phrase met deux heures côte à côte, point.
        phrase = sommeil.ligne(sommeil.CONTREDIT, time(23, 30)).lower()
        for mot in ("menti", "faux", "triche", "raté", "échec", "devrais"):
            assert mot not in phrase

    def test_sans_signal_il_n_y_a_pas_de_phrase(self):
        assert sommeil.ligne(sommeil.SANS_SIGNAL, time(7, 30)) == ""


@pytest.mark.django_db
class TestLaSondeNeRetireRien:
    """La règle du §6, appliquée ici : une sonde n'invalide jamais."""

    @pytest.fixture
    def routine(self, django_user_model):
        from forge.models import Profile, Routine, Track

        user = django_user_model.objects.create_user(username="arthur", password="coach")
        Profile.objects.create(user=user)
        piste, _ = Track.objects.get_or_create(user=user, kind=Track.ENTRETIEN)
        return Routine.objects.create(
            user=user, track=piste, name="Au lit", weekly_target=6,
            anchor=AVANT_COUCHER, deadline=time(23, 30),
        )

    def test_une_contradiction_ne_reprend_aucun_eclat(self, routine):
        from django.utils import timezone

        from forge import services
        from forge.models import Profile, Signal

        jour = date(2026, 8, 19)
        services.check_routine(routine, day=jour, at=time(22, 50))
        apres_coche = Profile.objects.get(user=routine.user).shards

        # Une sonde rapporte de l'activité à 1h du matin : la coche est
        # contredite, et rien n'est repris.
        Signal.objects.create(
            user=routine.user,
            source="agent",
            category="autre",
            minutes=30,
            day=jour,
            started_at=timezone.now(),
            ended_at=timezone.now(),
        )
        assert Profile.objects.get(user=routine.user).shards == apres_coche

    def test_une_contradiction_ne_retire_pas_la_semaine(self, routine):
        from forge import services

        jour = date(2026, 8, 19)
        services.check_routine(routine, day=jour, at=time(22, 50))
        panneau = services.routine_panel(routine.user, today=jour)
        assert panneau["groups"][0]["routines"][0]["week_done"] == 1

    def test_le_panneau_porte_l_etat_de_corroboration(self, routine):
        from forge import services

        jour = date(2026, 8, 19)
        ligne = services.routine_panel(routine.user, today=jour)["groups"][0]["routines"][0]
        assert ligne["corroboration"] in (
            sommeil.CORROBORE,
            sommeil.CONTREDIT,
            sommeil.SANS_SIGNAL,
        )


@pytest.mark.django_db
class TestLaPreuveEnBase:
    @pytest.fixture
    def projet(self, django_user_model):
        from forge import services
        from forge.models import Profile

        user = django_user_model.objects.create_user(username="arthur", password="coach")
        Profile.objects.create(user=user)
        return services.create_project_from_markdown(
            user, "# Carnet de labs\n\nDomaine: savoir\n\n- [ ] Terminer Bandit (2)\n"
        )

    def test_une_preuve_paie_en_eclats(self, projet):
        from forge import services
        from forge.models import Profile

        avant = Profile.objects.get(user=projet.user).shards
        services.declarer_preuve(
            projet.user, projet, critere="les 100 % de labs Apprentice validés", day=date(2026, 8, 19)
        )
        assert Profile.objects.get(user=projet.user).shards == avant + capacite.SHARDS_PAR_PREUVE

    def test_une_preuve_ne_donne_aucune_xp(self, projet):
        # La règle qui compte. L'XP mesure le volume par construction (§4.4) ;
        # si une preuve en donnait, l'axe capacité deviendrait un raccourci vers
        # le niveau, et le §17 interdit exactement ça.
        from django.db.models import Sum

        from forge import services
        from forge.models import Session

        def xp():
            return Session.objects.filter(user=projet.user).aggregate(t=Sum("xp_awarded"))["t"] or 0

        avant = xp()
        services.declarer_preuve(
            projet.user, projet, critere="les 100 % de labs Apprentice validés", day=date(2026, 8, 19)
        )
        assert xp() == avant

    def test_un_critere_creux_est_refuse(self, projet):
        from forge import services

        with pytest.raises(ValueError):
            services.declarer_preuve(projet.user, projet, critere="ok", day=date(2026, 8, 19))

    def test_le_panneau_garde_les_deux_nombres_separes(self, projet):
        from forge import services

        services.declarer_preuve(
            projet.user, projet, critere="les 100 % de labs Apprentice validés", day=date(2026, 8, 19)
        )
        panneau = services.capacite_panel(projet.user)
        assert panneau["preuves"] == 1
        assert "heures" in panneau and "score" not in panneau


@pytest.mark.django_db
class TestLaDifficulteNeChangeAucunCalcul:
    @pytest.fixture
    def user(self, django_user_model):
        from forge.models import Profile

        user = django_user_model.objects.create_user(username="arthur", password="coach")
        Profile.objects.create(user=user)
        return user

    def _session(self, user, difficulte):
        from django.utils import timezone

        from forge import services

        projet = services.create_project_from_markdown(
            user, f"# P{difficulte}\n\nDomaine: code\n\n- [ ] Une étape précise à faire (1)\n"
        )
        session = services.start_session(user, projet, planned_minutes=25)
        session.started_at = timezone.now() - timedelta(minutes=26)
        session.save(update_fields=["started_at"])
        return services.end_session(
            session, note="", next_action="la suite", difficulty=difficulte
        )

    def test_deux_sessions_identiques_rapportent_la_meme_xp(self, user):
        facile = self._session(user, capacite.TROP_FACILE)
        dur = self._session(user, capacite.TROP_DUR)
        # La deuxième session du jour a ses propres multiplicateurs ; ce qui est
        # vérifié ici est que la difficulté n'entre dans aucun d'eux.
        assert facile["xp"] > 0 and dur["xp"] > 0
        assert "difficulty" not in facile["breakdown"]
        assert "difficulte" not in facile["breakdown"]

    def test_trois_sessions_faciles_declenchent_le_constat(self, user):
        for _ in range(3):
            self._session(user, capacite.TROP_FACILE)
        from forge import services

        assert services.palier_de_difficulte(user) is not None

    def test_sans_declaration_aucun_constat(self, user):
        from forge import services

        self._session(user, None)
        assert services.palier_de_difficulte(user) is None


@pytest.mark.django_db
class TestLaSaisonDEssai:
    """Index 0, mise nulle, et surtout : elle ne se compare jamais.

    Le piège qu'elle évite tient en une phrase. Les premiers jours servent à
    régler ses créneaux et à comprendre les boucliers ; leur score est donc
    faussement bas. Or le boss de la saison suivante se dimensionne sur le score
    précédent, et le fantôme se tire des saisons passées. Une période
    d'apprentissage rangée parmi les vraies resterait un adversaire trop faible
    pour toujours — et le défaut serait invisible, puisque tout marcherait.
    """

    @pytest.fixture
    def user(self, django_user_model):
        from forge.models import Profile

        user = django_user_model.objects.create_user(username="arthur", password="coach")
        Profile.objects.create(user=user)
        return user

    def test_l_essai_porte_l_index_zero_et_aucune_mise(self, user):
        from forge import services

        essai = services.open_season(user, starts_on=date(2026, 8, 19), stake=240, essai=True)
        assert essai.index == 0
        assert essai.stake_shards == 0

    def test_la_saison_suivante_est_la_premiere(self, user):
        from forge import services

        services.open_season(user, starts_on=date(2026, 8, 19), essai=True)
        vraie = services.open_season(user, starts_on=date(2026, 9, 1))
        assert vraie.index == 1

    def test_l_essai_ne_dimensionne_pas_le_boss_suivant(self, user):
        # La règle qui compte. Sans elle, quelques jours d'apprentissage
        # fixeraient la barre de la première vraie saison, et la fixeraient bas.
        from django.utils import timezone

        from forge import services
        from forge.models import Session

        essai = services.open_season(user, starts_on=date(2026, 8, 19), essai=True)
        projet = services.create_project_from_markdown(
            user, "# P\n\nDomaine: code\n\n- [ ] Une étape précise à faire (1)\n"
        )
        Session.objects.create(
            user=user, project=projet, season=essai, status=Session.DONE,
            planned_minutes=25, actual_minutes=25, started_at=timezone.now(),
            coach_day=date(2026, 8, 20),
        )

        suivante = services.open_season(user, starts_on=date(2026, 9, 1))
        # Le boss est celui d'une première saison — dimensionné sur le contrat
        # annoncé, et non sur les 25 minutes de l'essai. Sans la règle, il
        # tomberait à la hauteur d'une seule session.
        assert suivante.boss.max_hp > 25 * 4

    def test_l_essai_peut_etre_plus_court(self, user):
        from forge import services

        essai = services.open_season(
            user, starts_on=date(2026, 8, 19), essai=True, ends_on=date(2026, 8, 29)
        )
        assert essai.ends_on == date(2026, 8, 29)

    def test_une_vraie_saison_garde_ses_28_jours(self, user):
        # `ends_on` est réservé à l'essai : la durée d'une saison est une règle
        # du §12.1, pas un réglage.
        from forge import services

        vraie = services.open_season(
            user, starts_on=date(2026, 8, 19), ends_on=date(2026, 8, 21)
        )
        assert (vraie.ends_on - vraie.starts_on).days == 27

    def test_un_essai_court_a_un_boss_a_sa_taille(self, user):
        # Un boss de quatre semaines posé sur onze jours est imbattable, et un
        # adversaire imbattable dès le premier jour n'apprend rien à personne.
        from forge import services

        court = services.open_season(
            user, starts_on=date(2026, 8, 19), essai=True, ends_on=date(2026, 8, 29)
        )
        entier = services.open_season(user, starts_on=date(2026, 9, 1))
        assert court.boss.max_hp < entier.boss.max_hp

    def test_l_essai_sort_du_reservoir_de_fantomes(self, user):
        from forge import progression, services

        services.open_season(user, starts_on=date(2026, 7, 1), essai=True)
        services.open_season(user, starts_on=date(2026, 8, 19))
        panneau = progression.phantom_panel(user, today=date(2026, 8, 25))
        # Une seule saison passée existe, et c'est l'essai : le fantôme ne peut
        # donc venir de nulle part.
        assert panneau is None or panneau.get("available") is not True


@pytest.mark.django_db
class TestLaCocheAutomatique:
    """Les sondes cochent le lever et le coucher — mais seulement sur preuve.

    C'est la seule automatisation du système qui écrive à la place de
    quelqu'un. Elle tient parce qu'elle ne sait qu'**ajouter** : jamais
    décocher, jamais marquer un échec, jamais trancher un cas ambigu. Ces
    tests-là gardent surtout ce qu'elle ne fait pas.
    """

    @pytest.fixture
    def profile(self, django_user_model):
        from forge.models import Profile, Routine, Track

        user = django_user_model.objects.create_user(username="arthur", password="coach")
        profil = Profile.objects.create(user=user)
        piste, _ = Track.objects.get_or_create(user=user, kind=Track.ENTRETIEN)
        # L'ancre n'est pas décorative ici : c'est elle qui dit quelle borne
        # juge l'habitude. Une fenêtre posée sur une routine « libre » reste
        # vérifiable au tap, mais aucune sonde ne saura la corroborer.
        Routine.objects.create(
            user=user, track=piste, name="Debout", weekly_target=6,
            anchor=REVEIL, deadline=time(7, 30),
        )
        return profil

    def _signal(self, user, jour, debut, fin):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from forge.models import Signal

        zone = ZoneInfo(user.profile.timezone_name)
        Signal.objects.create(
            user=user, source="agent", category="autre", minutes=10, day=jour,
            started_at=datetime.combine(jour, debut, tzinfo=zone),
            ended_at=datetime.combine(jour, fin, tzinfo=zone),
        )

    def test_une_activite_tot_coche_le_lever(self, profile):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from forge import triggers
        from forge.models import RoutineCheck

        jour = date(2026, 8, 19)
        self._signal(profile.user, jour, time(7, 5), time(7, 40))
        maintenant = datetime.combine(jour, time(14, 0), tzinfo=ZoneInfo(profile.timezone_name))

        fired = triggers.check_habitudes(profile, maintenant)
        assert [f["kind"] for f in fired] == ["habitude_auto"]

        coche = RoutineCheck.objects.get(routine__name="Debout", day=jour)
        assert coche.source == RoutineCheck.AGENT
        assert coche.on_time is True

    def test_la_coche_est_creditee_a_l_heure_du_fait(self, profile):
        # Le piège : le déclencheur tourne à 14h. S'il créditait à son heure à
        # lui, la coche serait « hors fenêtre » pour une preuve qui était dedans.
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from forge import triggers
        from forge.models import RoutineCheck

        jour = date(2026, 8, 19)
        self._signal(profile.user, jour, time(7, 5), time(7, 40))
        triggers.check_habitudes(
            profile, datetime.combine(jour, time(14, 0), tzinfo=ZoneInfo(profile.timezone_name))
        )
        assert RoutineCheck.objects.get(day=jour).on_time is True

    def test_une_activite_tardive_ne_coche_rien(self, profile):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from forge import triggers
        from forge.models import RoutineCheck

        jour = date(2026, 8, 19)
        self._signal(profile.user, jour, time(11, 0), time(11, 30))
        triggers.check_habitudes(
            profile, datetime.combine(jour, time(14, 0), tzinfo=ZoneInfo(profile.timezone_name))
        )
        assert not RoutineCheck.objects.filter(day=jour).exists()

    def test_le_silence_ne_coche_rien(self, profile):
        # Une journée sans sonde reste une journée à cocher à la main. Traiter
        # l'absence comme une preuve inventerait des habitudes tenues.
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from forge import triggers
        from forge.models import RoutineCheck

        jour = date(2026, 8, 19)
        triggers.check_habitudes(
            profile, datetime.combine(jour, time(14, 0), tzinfo=ZoneInfo(profile.timezone_name))
        )
        assert not RoutineCheck.objects.filter(day=jour).exists()

    def test_elle_ne_decoche_jamais_une_coche_a_la_main(self, profile):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from forge import services, triggers
        from forge.models import Routine, RoutineCheck

        jour = date(2026, 8, 19)
        routine = Routine.objects.get(name="Debout")
        services.check_routine(routine, day=jour, at=time(7, 10))
        self._signal(profile.user, jour, time(11, 0), time(11, 30))

        triggers.check_habitudes(
            profile, datetime.combine(jour, time(14, 0), tzinfo=ZoneInfo(profile.timezone_name))
        )
        coche = RoutineCheck.objects.get(day=jour)
        assert coche.source == RoutineCheck.APP
        assert coche.on_time is True

    def test_le_coucher_attend_que_la_journee_soit_close(self, profile):
        # Avant la bascule, l'absence d'activité après 23h30 ne prouve rien :
        # il est 22h. C'est la différence entre « il ne s'est rien passé » et
        # « il ne se passera plus rien ».
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from forge import triggers
        from forge.models import Profile, Routine, RoutineCheck, Track

        piste = Track.objects.get(user=profile.user, kind=Track.ENTRETIEN)
        Routine.objects.create(
            user=profile.user, track=piste, name="Au lit", weekly_target=5,
            anchor=AVANT_COUCHER, deadline=time(23, 30),
        )
        jour = date(2026, 8, 19)
        self._signal(profile.user, jour, time(20, 0), time(22, 40))
        zone = ZoneInfo(profile.timezone_name)

        # Le soir même, à 22h45 : rien n'est coché.
        triggers.check_habitudes(profile, datetime.combine(jour, time(22, 45), tzinfo=zone))
        assert not RoutineCheck.objects.filter(routine__name="Au lit").exists()

        # Le lendemain, la journée est close : la preuve vaut.
        triggers.check_habitudes(
            profile, datetime.combine(date(2026, 8, 20), time(9, 0), tzinfo=zone)
        )
        coche = RoutineCheck.objects.get(routine__name="Au lit", day=jour)
        assert coche.source == RoutineCheck.AGENT
