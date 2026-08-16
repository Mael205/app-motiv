"""Un état de démonstration, pour regarder l'interface remplie.

Sert à une chose : pouvoir **voir** les écrans du §12 avec du contenu — arbre
qui a poussé, cartes obtenues, reliques, chaleur allumée. Une interface de jeu
jugée sur des compteurs à zéro se conçoit mal, parce que tout y semble calme et
que les problèmes de densité n'apparaissent jamais.

Écrit sur un utilisateur **séparé** (``demo``), jamais sur le compte réel : un
outil de mise au point qui touche aux vraies données finit toujours par en
effacer, et le §17 interdit de faire disparaître du travail réel.

    python manage.py demodata          # crée ou remet à neuf
    python manage.py demodata --clear  # supprime tout
"""

from __future__ import annotations

import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from forge import progression, services
from forge.models import (
    Garde,
    GardeDay,
    Profile,
    Project,
    RoadmapStep,
    Routine,
    RoutineCheck,
    Session,
    Track,
)
from forge.rules import loot as loot_rules
from forge.rules import routines as routine_rules
from forge.rules import skills as skill_rules
from forge.rules.calendar import coach_day

DEMO = "demo"

# Un profil de travail plausible : un dominant, un secondaire, un à l'arrêt.
# C'est cette asymétrie qu'on veut voir à l'écran — un arbre équilibré ne
# montrerait pas ce que l'arbre sert à montrer (§12.9).
PROJETS = [
    ("Evolve — prototype 4v1", skill_rules.MOTEUR_DE_JEU, "code", 1, 62),
    ("Bestiaire — app mobile", skill_rules.WEB, "code", 2, 28),
    ("Roadmap cybersécurité", skill_rules.CYBER, "savoir", 3, 11),
    ("Danse", skill_rules.CORPS, "corps", 1, 9),
]


class Command(BaseCommand):
    help = "Crée un utilisateur « demo » avec un état de jeu rempli."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="supprime l'utilisateur demo")
        parser.add_argument(
            "--ended",
            action="store_true",
            help="termine la saison courante, pour voir la cérémonie du §7.4",
        )

    def handle(self, *args, **options):
        User = get_user_model()

        existant = User.objects.filter(username=DEMO).first()
        if existant:
            # ``Track.user`` et ``Project.user`` sont en PROTECT — c'est
            # volontaire côté modèle : personne ne doit pouvoir effacer des
            # heures de travail par une suppression en cascade (§17). Il faut
            # donc démonter dans l'ordre, explicitement.
            Session.objects.filter(user=existant).delete()
            Project.objects.filter(user=existant).delete()
            Routine.objects.filter(user=existant).delete()
            Track.objects.filter(user=existant).delete()
            existant.delete()
            self.stdout.write("ancien état demo supprimé")
        if options["clear"]:
            return

        user = User.objects.create_user(username=DEMO, password=DEMO)
        profile = Profile.objects.create(user=user)
        today = coach_day(timezone.now(), profile.timezone_name, profile.day_rollover_hour)

        atelier, _ = Track.objects.get_or_create(user=user, kind=Track.ATELIER)
        corps, _ = Track.objects.get_or_create(user=user, kind=Track.CORPS)

        # Une saison close avant la courante : sans elle le fantome du §12.7
        # n'a aucun adversaire, et on ne verrait jamais le trace de la course.
        passee = services.open_season(user, starts_on=today - timedelta(days=45), stake=100)
        passee.status = passee.CLOSED
        passee.ends_on = today - timedelta(days=18)
        passee.save(update_fields=["status", "ends_on"])

        services.open_season(user, starts_on=today - timedelta(days=9), stake=120)
        saison = services.current_season(user, today=today)

        rng = random.Random(7)
        total = 0

        for nom, branche, domaine, slot, seances in PROJETS:
            piste = corps if domaine == "corps" else atelier
            projet = Project.objects.create(
                user=user,
                track=piste,
                name=nom,
                branch=branche,
                domain=domaine,
                slot=slot,
                weekly_commitment=3,
            )
            for i in range(4):
                RoadmapStep.objects.create(
                    project=projet,
                    label=f"Étape {i + 1} de {nom}",
                    order=i,
                    state=RoadmapStep.DOING if i == 0 else RoadmapStep.TODO,
                    estimated_sessions=2,
                )

            # Les séances sont étalées sur deux mois pour que l'arbre ait de
            # quoi montrer, et écrites directement : passer par end_session
            # rejouerait tout le calcul d'XP pour des données jetables.
            for n in range(seances):
                jour = today - timedelta(days=rng.randint(0, 58))
                minutes = rng.choice([25, 25, 50, 10, 50])
                debut = timezone.now() - timedelta(days=(today - jour).days, hours=rng.randint(1, 6))
                Session.objects.create(
                    user=user,
                    project=projet,
                    season=saison,
                    planned_minutes=minutes,
                    actual_minutes=minutes,
                    status=Session.DONE,
                    coach_day=jour,
                    started_at=debut,
                    ended_at=debut + timedelta(minutes=minutes),
                    rank_in_day=1,
                    xp_awarded=minutes + 20,
                )
                total += minutes

        # Six des sept derniers jours travaillés : la braise est presque au
        # maximum, avec un jour manqué visible — c'est l'état intéressant, pas
        # une série parfaite qui ne montrerait pas le refroidissement.
        for i in range(7):
            if i == 3:
                continue
            jour = today - timedelta(days=i)
            if not Session.objects.filter(user=user, coach_day=jour).exists():
                projet = Project.objects.filter(user=user).first()
                debut = timezone.now() - timedelta(days=i, hours=3)
                Session.objects.create(
                    user=user,
                    project=projet,
                    season=saison,
                    planned_minutes=25,
                    actual_minutes=25,
                    status=Session.DONE,
                    coach_day=jour,
                    started_at=debut,
                    ended_at=debut + timedelta(minutes=25),
                    rank_in_day=1,
                    xp_awarded=45,
                )

        # Routines et gardes : sans elles le rail droit du HUD est vide, et on
        # jugerait une mise en page sur un cas qui n'arrive jamais en vrai.
        piste_entretien, _ = Track.objects.get_or_create(user=user, kind=Track.ENTRETIEN)
        for nom, ancre, jours, cible in (
            ("Skincare du matin", routine_rules.REVEIL, [0, 1, 2, 3, 4, 5, 6], 5),
            ("Étirements", routine_rules.FIN_DE_SESSION, [0, 1, 2, 3, 4], 4),
            ("Skincare du soir", routine_rules.AVANT_COUCHER, [0, 1, 2, 3, 4, 5, 6], 6),
        ):
            routine = Routine.objects.create(
                user=user,
                track=piste_entretien,
                name=nom,
                anchor=ancre,
                weekdays=jours,
                weekly_target=cible,
            )
            for i in range(cible - 1):
                RoutineCheck.objects.get_or_create(
                    routine=routine, day=today - timedelta(days=i), defaults={"shards_awarded": 2}
                )

        for nom, budget in (("Réseaux sociaux", 2), ("Scroll passif le soir", 2), ("Porno", 1)):
            garde = Garde.objects.create(user=user, name=nom, weekly_budget=budget)
            for i in (1, 4, 9, 12):
                GardeDay.objects.get_or_create(
                    garde=garde, day=today - timedelta(days=i), defaults={"occurred": i % 3 == 0}
                )

        for _ in range(9):
            progression.draw_card(user, reason=loot_rules.CLOTURE_DE_SEMAINE, rng=rng)
        progression.grant_relics_for(user, ["increvable", "retour_du_neant"])

        if options["ended"]:
            # La saison se termine hier : la cérémonie du §7.4 se déclenche à
            # la prochaine ouverture de l'app. Le boss est laissé debout pour
            # voir le titre raté, qui est celui qu'on oublie de regarder.
            saison.ends_on = today - timedelta(days=1)
            saison.save(update_fields=["ends_on"])
            self.stdout.write("saison terminée : la cérémonie se jouera à l'ouverture")

        arbre = progression.skill_tree(user)
        self.stdout.write(
            self.style.SUCCESS(
                f"demo / demo — {total} minutes, "
                f"{sum(1 for b in arbre['branches'] if b['minutes'])} branches actives, "
                f"{user.cards.count()} cartes, {user.relics.count()} reliques"
            )
        )
