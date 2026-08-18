"""Le contrat de saison signé (ajout du 17 août 2026).

Un engagement hebdomadaire existait déjà : un nombre par projet, modifiable
dans un écran de réglages. Le problème n'est pas le nombre, il est le geste. On
ne se souvient pas d'avoir réglé un curseur, et ce dont on ne se souvient pas
ne se tient pas. Trois semaines plus tard, « je m'étais engagé à quoi, déjà ? »
n'a pas de réponse — donc il n'y avait pas d'engagement, seulement un
paramètre.

Le contrat est le même nombre, pris autrement. Trois différences, et chacune
fait la totalité de la valeur :

- **ses termes sont écrits en toutes lettres au moment de signer**. Pas « 3 »
  dans un champ, mais « douze sessions en quatre semaines, sur ces projets-là ».
  Un total sur la saison entière se pèse ; un nombre par semaine ne se pèse pas ;
- **il est daté et il ne bouge plus**. Baisser un engagement en cours de semaine
  reste possible et reste sain (§4.3 étendu) — mais le contrat, lui, garde ce
  qui a été signé. Sans quoi la fin de saison se compare à une cible déplacée en
  route, et la comparaison ne vaut rien ;
- **il se relit à la clôture**, sans jugement. Le §17 interdit le reproche : le
  contrat rend un écart, pas une note. « Signé 12, fait 9 » est un fait.

Il ne bloque rien. Une saison peut s'ouvrir sans contrat — refuser d'ouvrir
tant que quelqu'un n'a pas signé transformerait le rituel en formulaire, et un
formulaire se remplit sans le lire.
"""

from __future__ import annotations

from dataclasses import dataclass

# Zéro n'est pas un engagement, c'est un abandon déguisé en réglage — la même
# règle qu'au §4.3 pour l'engagement hebdomadaire.
MINIMUM = 1

# Au-delà de deux par jour en moyenne, ce n'est plus un contrat, c'est le
# sur-régime du §0.2 signé d'avance. Le plafond de régime le rattraperait de
# toute façon en n'en payant que trois par jour : autant le dire avant.
MAXIMUM = 14


@dataclass(frozen=True)
class Verdict:
    ok: bool
    raison: str = ""


@dataclass(frozen=True)
class Contrat:
    """Ce qui est signé, et ce que ça fait sur la saison entière."""

    sessions_par_semaine: int
    projets: tuple[str, ...]
    semaines: int

    @property
    def total(self) -> int:
        return self.sessions_par_semaine * self.semaines

    @property
    def lignes(self) -> tuple[str, ...]:
        """Les termes, en toutes lettres. C'est ce qu'on lit avant de signer."""
        projets = ", ".join(self.projets) if self.projets else "tes projets actifs"
        return (
            f"{self.sessions_par_semaine} sessions par semaine, pendant "
            f"{self.semaines} semaines.",
            f"Soit {self.total} sessions au total, sur : {projets}.",
            "Le nombre ne bougera plus. Tu peux baisser un engagement en cours "
            "de route, le contrat gardera ce que tu as signé aujourd'hui.",
            "À la clôture, tu liras l'écart. Pas une note — un écart.",
        )


def verifier(sessions_par_semaine: int) -> Verdict:
    if sessions_par_semaine < MINIMUM:
        return Verdict(
            False,
            "Zéro n'est pas un engagement. Si la saison doit être vide, ne "
            "l'ouvre pas — c'est plus honnête, et ça ne coûte rien.",
        )
    if sessions_par_semaine > MAXIMUM:
        return Verdict(
            False,
            f"{sessions_par_semaine} par semaine, maximum {MAXIMUM}. Au-delà, le "
            "plafond de régime n'en paiera que trois par jour : tu signerais "
            "pour du travail que le système ne comptera pas.",
        )
    return Verdict(True)


def bilan(*, signe: int, fait: int) -> str:
    """La relecture à la clôture. Un écart, jamais une note.

    Aucun adjectif, aucun adverbe d'intensité : « seulement », « à peine » et
    « déjà » portent tous un jugement que le §17 interdit au système.
    """
    if fait >= signe:
        return f"Contrat signé : {signe} sessions. Faites : {fait}."
    return f"Contrat signé : {signe} sessions. Faites : {fait}. Écart : {signe - fait}."
