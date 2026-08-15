/**
 * Lecture du temps d'écran Android et envoi au coach (SPEC §9.2).
 *
 * ATTENTION : ce fichier n'a été ni compilé ni exécuté — il a été écrit sur une
 * machine sans SDK Android. C'est un point de départ relu, pas du code livré.
 * Voir README.md.
 *
 * Le principe est le même que sur les autres sondes : la catégorisation se fait
 * **ici**, sur le téléphone. Le serveur reçoit « scroll_passif : 47 minutes »
 * et n'apprend jamais quelle application (SPEC §11.10). Le nom du paquet ne
 * quitte pas l'appareil.
 */

package com.coach.mobile

import android.app.usage.UsageStatsManager
import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.TimeUnit

/** Catégories connues du serveur. Toute autre valeur sera refusée à l'ingestion. */
object Categories {
    const val TRAVAIL = "travail_hors_projet"
    const val RESEAUX = "reseaux"
    const val SCROLL = "scroll_passif"
    const val ADULTE = "adulte"
    const val JEU = "jeu"
    const val SPORT = "sport"
    const val AUTRE = "autre"
}

/**
 * Table paquet → catégorie. Elle vit sur le téléphone et n'est jamais envoyée.
 *
 * `adulte` est volontairement vide : cette liste regarde l'utilisateur, à lui
 * de la remplir depuis l'écran de réglages.
 */
val DEFAULT_RULES: Map<String, List<String>> = mapOf(
    Categories.RESEAUX to listOf(
        "com.instagram.android",
        "com.twitter.android",
        "com.snapchat.android",
        "com.facebook.katana",
        "com.linkedin.android",
    ),
    Categories.SCROLL to listOf(
        "com.zhiliaoapp.musically",   // TikTok
        "com.reddit.frontpage",
        "tv.twitch.android.app",
    ),
    Categories.ADULTE to emptyList(),
    Categories.JEU to listOf("com.ankama.dofustouch"),
    Categories.SPORT to listOf("com.strava", "com.google.android.apps.fitness"),
)

/** Seuil en dessous duquel un passage n'est pas un usage (aligné sur le serveur). */
const val MIN_MINUTES = 3

class UsageStatsReader(
    private val context: Context,
    private val rules: Map<String, List<String>> = DEFAULT_RULES,
) {

    private fun categoryOf(packageName: String): String {
        for ((category, packages) in rules) {
            if (packages.any { packageName.equals(it, ignoreCase = true) }) return category
        }
        return Categories.AUTRE
    }

    /**
     * Minutes par catégorie sur les dernières [hours] heures.
     *
     * `queryAndAggregateUsageStats` rend un total par paquet ; on le replie sur
     * les catégories avant toute sortie de l'appareil.
     */
    fun minutesByCategory(hours: Long = 24): Map<String, Int> {
        val manager = context.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
        val end = System.currentTimeMillis()
        val start = end - TimeUnit.HOURS.toMillis(hours)

        val totals = mutableMapOf<String, Long>()
        for ((packageName, stats) in manager.queryAndAggregateUsageStats(start, end)) {
            val category = categoryOf(packageName)
            if (category == Categories.AUTRE) continue          // jamais envoyé
            totals[category] = (totals[category] ?: 0L) + stats.totalTimeInForeground
        }

        return totals
            .mapValues { (_, millis) -> TimeUnit.MILLISECONDS.toMinutes(millis).toInt() }
            .filterValues { it >= MIN_MINUTES }
    }

    /**
     * Poste les totaux. Rend `true` si le serveur a accepté.
     *
     * Un 401 signifie que le jeton est mort : l'appelant doit arrêter de
     * réessayer et demander un nouveau jeton, pas boucler sur un secret périmé.
     */
    fun post(apiUrl: String, token: String, entries: Map<String, Int>): Boolean {
        if (entries.isEmpty()) return true

        val body = JSONObject().apply {
            put("source", "mobile")
            put("entries", JSONArray().apply {
                entries.forEach { (category, minutes) ->
                    put(JSONObject().put("category", category).put("minutes", minutes))
                }
            })
        }

        val connection = (URL("${apiUrl.trimEnd('/')}/api/signals").openConnection() as HttpURLConnection)
        return try {
            connection.requestMethod = "POST"
            connection.doOutput = true
            connection.connectTimeout = 10_000
            connection.readTimeout = 10_000
            connection.setRequestProperty("Content-Type", "application/json")
            connection.setRequestProperty("X-Probe-Token", token)
            connection.outputStream.use { it.write(body.toString().toByteArray()) }
            connection.responseCode in 200..299
        } catch (error: Exception) {
            false
        } finally {
            connection.disconnect()
        }
    }
}
