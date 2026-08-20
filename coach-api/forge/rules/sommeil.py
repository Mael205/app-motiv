"""Lever et coucher : ce qu'une déclaration prouve, et ce qu'elle ne prouve pas.

Le §11.9 ancre les routines sur un geste et non sur une heure, et il a raison
pour presque tout — « après la douche » arrive au bon moment sans réveil. Deux
habitudes échappent à la règle parce que **l'heure est l'habitude**. Elles
posent alors une question que les autres routines ne posent pas : qu'est-ce qui
empêche de cocher « debout » à 14h ?

Trois réponses, dans l'ordre de leur force.

1. **L'heure du geste, qui n'est pas déclarée mais constatée.** Le §6 refuse
   qu'on saisisse une session après coup, pour la même raison : une session
   commence quand on appuie. Ici c'est identique — on ne peut pas cocher
   « debout » à 7h20 en dormant. La fenêtre du §11.9 étendu s'applique au
   moment du clic, jamais à une heure qu'on tape. C'est déjà l'essentiel de la
   preuve pour le **lever**.

2. **Ce que les sondes ont vu.** L'agent PC et AdGuard datent l'activité de la
   journée. Une première activité à 7h05 corrobore « debout avant 7h30 ». Une
   activité à 1h12 contredit « au lit avant 23h30 ».

3. **Rien du tout**, et il faut le dire aussi. Se lever tôt sans toucher un
   écran ne laisse aucune trace, et c'est plutôt bon signe.

**Ce que la corroboration ne fait jamais.** Le §6 est explicite : la preuve
d'activité « n'invalide jamais une session ». La même règle s'applique ici, et
elle vaut dans les deux sens :

* une contradiction **ne retire rien** — ni Éclats, ni semaine tenue. Elle est
  affichée comme un fait, sans adjectif, et l'utilisateur en fait ce qu'il veut.
  Un PC resté allumé la nuit, un téléphone qui se synchronise, une soirée chez
  quelqu'un : trois façons d'être contredit à tort, et une sanction automatique
  sur ce genre de signal serait désinstallée dans la semaine ;
* une corroboration **ne paie rien** non plus. Payer la corroboration
  reviendrait à payer le fait d'avoir laissé une sonde tourner, donc à
  récompenser l'équipement plutôt que l'habitude.

Elle se calcule **à la lecture**, jamais à l'écriture : un coucher ne peut être
corroboré qu'une fois la nuit passée, et un état figé au moment du clic serait
faux pour l'habitude la plus importante des deux.
"""

from __future__ import annotations

from datetime import time

from .calendar import ROLLOVER_HOUR
from .routines import AVANT, AVANT_COUCHER, REVEIL, minutes_since_rollover

CORROBORE = "corrobore"
CONTREDIT = "contredit"
SANS_SIGNAL = "sans_signal"

LABELS = {
    CORROBORE: "corroboré par les sondes",
    CONTREDIT: "les sondes disent autre chose",
    SANS_SIGNAL: "aucune sonde n'a rien vu",
}


def _borne_qui_juge(
    anchor: str, premiere_activite: time | None, derniere_activite: time | None
) -> time | None:
    """Laquelle des deux bornes juge cette habitude ?

    **C'est l'ancre qui décide, et rien d'autre.** Une première version lisait
    les deux bornes pour toute habitude ; elle cochait « au lit avant 23h30 »
    dès qu'une activité était vue à 20h, puisque 20h tombe bien avant 23h30.
    La borne était dans la fenêtre, la conclusion absurde : être devant son
    écran à 20h ne prouve rien sur l'heure du coucher.

    Le lever se juge sur le **début** de la journée, le coucher sur sa **fin**.
    Les autres ancres — après la douche, en fin de session — ne se jugent pas :
    aucune sonde ne voit une douche.
    """
    if anchor == REVEIL:
        return premiere_activite
    if anchor == AVANT_COUCHER:
        return derniere_activite
    return None


def corroboration(
    deadline: time | None,
    direction: str,
    anchor: str = REVEIL,
    *,
    premiere_activite: time | None = None,
    derniere_activite: time | None = None,
    journee_finie: bool = False,
    rollover_hour: int = ROLLOVER_HOUR,
) -> str:
    """Ce que les sondes disent d'une habitude horaire, sur une journée donnée.

    **La règle qui gouverne tout le reste : une preuve positive contredit, une
    absence jamais.** Elle a l'air d'un détail et c'est la seule chose qui
    empêche cette mécanique de mentir.

    Le cas qui l'a imposée est arrivé le jour même de son écriture. La sonde web
    a été installée à 17h ; le matin, elle ne tournait pas. La première activité
    observée de la journée était donc 17h48, et l'habitude « debout avant
    7h30 » s'affichait *contredite* — alors que rien n'avait été observé du
    tout avant 17h. Une activité tardive ne dit pas « il s'est levé tard », elle
    dit « je n'ai rien vu plus tôt », ce qui est une absence.

    D'où l'asymétrie entre les deux habitudes :

    * **le lever** ne peut être que corroboré ou muet. Une activité à 7h05
      prouve qu'on était debout ; rien avant 7h30 ne prouve rien du tout — se
      lever tôt sans toucher un écran ne laisse aucune trace ;
    * **le coucher** peut être contredit, parce qu'une activité observée à 1h12
      est une preuve *positive* d'être éveillé. Mais il ne se juge qu'une fois
      la journée close : avant la bascule, un silence après 23h30 ne veut rien
      dire, il est 22h.
    """
    if deadline is None:
        return SANS_SIGNAL

    borne = _borne_qui_juge(anchor, premiere_activite, derniere_activite)
    if borne is None:
        return SANS_SIGNAL

    limite = minutes_since_rollover(deadline, rollover_hour)
    pose = minutes_since_rollover(borne, rollover_hour)
    dans_la_fenetre = pose <= limite if direction == AVANT else pose >= limite

    if dans_la_fenetre:
        # Le coucher tenu ne se sait qu'une fois la soirée passée.
        if anchor == AVANT_COUCHER and not journee_finie:
            return SANS_SIGNAL
        return CORROBORE

    # Hors fenêtre : contredire demande une preuve positive, et seule la fin de
    # journée en est une. Une première activité tardive est un silence, pas un
    # constat.
    if anchor == AVANT_COUCHER and journee_finie:
        return CONTREDIT
    return SANS_SIGNAL


def coche_automatique(
    deadline: time | None,
    direction: str,
    anchor: str = REVEIL,
    *,
    premiere_activite: time | None = None,
    derniere_activite: time | None = None,
    journee_finie: bool = False,
    rollover_hour: int = ROLLOVER_HOUR,
) -> time | None:
    """L'heure qui prouve l'habitude, si les sondes suffisent à cocher seules.

    Elle rend **le moment**, et non un oui/non, parce que la coche doit être
    créditée à l'heure du fait et pas à celle du traitement. Un déclencheur qui
    tourne à 14h et crédite « debout » à 14h enregistrerait une coche hors
    fenêtre pour une preuve qui, elle, était dans la fenêtre.

    Elles ne cochent que sur une **preuve positive**, jamais sur un silence, et
    ne décochent jamais rien. Trois cas seulement :

    * **le lever**, dès que la première activité tombe dans la fenêtre. Une
      activité observée à 7h05 prouve qu'on était debout à 7h05 — c'est plus
      solide qu'un tap, qu'on peut faire en se recouchant ;
    * **le coucher**, mais seulement une fois la journée finie. Avant la
      bascule, l'absence d'activité après 23h30 ne prouve rien : il est 22h.
      C'est la différence entre « il ne s'est rien passé » et « il ne se passera
      plus rien », et c'est toute la différence ;
    * **rien du tout**, dès qu'aucune sonde n'a rien vu. Une journée sans
      signal reste à cocher à la main.

    Ce qu'elle ne fait jamais : décocher, marquer un échec, ou trancher un cas
    ambigu. Le §6 interdit qu'une sonde invalide quoi que ce soit, et une
    automatisation qui se trompe contre l'utilisateur se fait désinstaller bien
    avant d'avoir servi.
    """
    if deadline is None or direction != AVANT:
        return None

    # Le coucher ne se juge qu'une fois la journée close. Avant la bascule,
    # l'absence d'activité après 23h30 ne prouve rien : il est 22h.
    if anchor == AVANT_COUCHER and not journee_finie:
        return None

    borne = _borne_qui_juge(anchor, premiere_activite, derniere_activite)
    if borne is None:
        return None

    limite = minutes_since_rollover(deadline, rollover_hour)
    if minutes_since_rollover(borne, rollover_hour) <= limite:
        return borne
    return None


def ligne(etat: str, deadline: time | None) -> str:
    """Le fait, écrit sans adjectif. Vide quand il n'y a rien à dire.

    Le §14 interdit le mot de jugement dans un texte affiché, et « tu as menti »
    en est un. Le constat se contente de mettre les deux heures côte à côte.
    """
    if deadline is None or etat == SANS_SIGNAL:
        return ""
    heure = f"{deadline.hour}h{deadline.minute:02d}".replace("h00", "h")
    if etat == CORROBORE:
        return f"Les sondes vont dans le même sens que la coche de {heure}."
    return f"Une activité a été observée après {heure}."
