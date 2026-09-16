"""Le projet du jour — ce que la journée demande, et rien d'autre.

*(Tranché le 13 septembre 2026, contre le §11.1 tel qu'il était écrit.)*

L'app **ne sait pas** quelle tâche précise il faut faire. La roadmap change en
cours de route, le travail réel déborde de ce qui était prévu, et aucune tâche
ne se vérifie de l'extérieur. Un système qui impose quand même une tâche se
retrouve donc avec une consigne fausse ou invérifiable, et il apprend à la
contourner — c'est le défaut de conception que ce module remplace.

Ce qui se vérifie, c'est **sur quoi** et **combien de temps**. La contrainte
tient donc en une phrase : chaque projet qui a un rendez-vous aujourd'hui veut
ses vingt-cinq minutes. La tâche, elle, redevient ce qu'elle aurait toujours dû
être — la note qu'on s'est laissée à soi-même à la fin de la séance précédente.

Trois conséquences, et elles sont dans les règles ci-dessous :

- **un jour sans rendez-vous est un jour libre.** Rien n'est dû, rien ne se
  bloque. La contrainte vient du contrat qu'on a signé au calme, jamais de
  l'app qui voudrait qu'on travaille tous les soirs ;
- **travailler ailleurs ne libère pas la soirée.** Les minutes posées sur un
  autre projet comptent partout ailleurs — XP, heures, boss —, mais le
  rendez-vous du jour reste dû. Sans cela, un créneau n'est qu'une préférence ;
- **le temps fait foi, pas la déclaration.** Vingt-cinq minutes sur le bon
  projet, mesurées par le serveur, et la soirée est tenue.
"""

from __future__ import annotations

from dataclasses import dataclass

# Le plancher du rendez-vous. Volontairement le même que la session normale du
# §4.1 : deux seuils différents pour la même soirée seraient impossibles à
# tenir en tête, et c'est la soirée qu'on regarde à 21h, pas le barème.
MINUTES_REQUISES = 25

# L'heure où ce qui n'est pas fait se voit. Fixe, et pas « fin de fenêtre moins
# quatre-vingt-dix minutes » : une heure qu'on ne peut pas réciter de mémoire
# n'est pas un rendez-vous, c'est un calcul.
HEURE_DE_BLOCAGE = 21


@dataclass(frozen=True)
class Attendu:
    """Un projet qui a rendez-vous aujourd'hui, et où il en est."""

    project_id: int
    name: str
    minutes: int
    heure: str = ""
    # Ce que ce rendez-vous demande **ce soir**. Vingt-cinq minutes par défaut ;
    # une carte « Petit pas » descend la barre à quinze pour la journée (§12.6).
    requis: int = MINUTES_REQUISES

    @property
    def fait(self) -> bool:
        return self.minutes >= self.requis

    @property
    def restantes(self) -> int:
        return max(0, self.requis - self.minutes)


@dataclass(frozen=True)
class Jour:
    """L'état de la journée, tel que l'accueil et le blocage le lisent."""

    attendus: tuple[Attendu, ...]

    @property
    def libre(self) -> bool:
        """Aucun rendez-vous : rien n'est dû, et rien ne se bloque."""
        return not self.attendus

    @property
    def restants(self) -> tuple[Attendu, ...]:
        return tuple(a for a in self.attendus if not a.fait)

    @property
    def tenu(self) -> bool:
        """Vrai dès qu'il n'y a plus rien à faire — jour libre compris."""
        return not self.restants

    @property
    def minutes(self) -> int:
        return sum(a.minutes for a in self.attendus)


def evaluer(attendus: list[Attendu]) -> Jour:
    return Jour(attendus=tuple(attendus))


def phrase(jour: Jour) -> str:
    """Ce que l'écran dit de la journée. Un constat, jamais un reproche.

    Le §14 et le §17 interdisent le jugement, et c'est ici qu'il s'inviterait le
    plus facilement : c'est la ligne qu'on lit le soir où l'on n'a rien fait.
    """
    if jour.libre:
        return "Aucun projet prévu aujourd'hui. Soirée libre."
    if jour.tenu:
        noms = ", ".join(a.name for a in jour.attendus)
        return f"Fait : {noms}."
    restant = jour.restants
    if len(restant) == 1:
        a = restant[0]
        if a.minutes:
            return f"{a.name} : {a.minutes} min posées, {a.restantes} pour tenir la journée."
        return f"{a.name} : {a.requis} min pour tenir la journée."
    noms = ", ".join(a.name for a in restant)
    return f"{len(restant)} rendez-vous à tenir : {noms}."
